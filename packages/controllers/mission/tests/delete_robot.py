"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    https://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

SPDX-License-Identifier: Apache-2.0
"""
import time
import unittest

from cloud_common import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from cloud_common.objects import mission as mission_object
from cloud_common.objects import robot as robot_object

from packages.controllers.mission.tests import test_context


class TestDeleteRobot(unittest.TestCase):
    def test_delete_idle_robot(self):
        """ Test if an idle robot is correctly deleted """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            # Check that the robot has been populated in the database
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)
            
            time.sleep(8)
            # Delete robot
            ctx.db_client.delete(api_objects.RobotObjectV1, "test01")
            
            # Wait and verify robot is deleted (check multiple times as simulator might recreate)
            for _ in range(240):  # Try for 120 seconds
                time.sleep(0.5)
                robots = ctx.db_client.list(api_objects.RobotObjectV1)
                if len(robots) == 0:
                    break
            
            # Final check
            robots = ctx.db_client.list(api_objects.RobotObjectV1)
            if len(robots) > 0:
                robot_names = [r.name for r in robots]
                self.fail(f"Expected 0 robots after deletion, found {len(robots)}: {robot_names}")

    def test_delete_on_task_robot(self):
        """ Test if the server kills the robot correctly when the robot is executing a mission """
        MISSION_DEFAULT_X = 50
        MISSION_DEFAULT_Y = 50
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)
            mission = test_context.mission_from_waypoint(
                "test01", MISSION_DEFAULT_X, MISSION_DEFAULT_Y)
            ctx.db_client.create(mission)

            # Watch, and break when robot is officially ON_TASK / mission is RUNNING
            for update in ctx.db_client.watch(api_objects.RobotObjectV1):
                if update.status.state == robot_object.RobotStateV1.ON_TASK:
                    break

            ctx.db_client.delete(api_objects.RobotObjectV1, "test01")

            # Server may set PENDING_DELETE then delete after failing the mission, or
            # process so fast that the robot is already gone. Poll briefly to allow
            # either outcome and avoid flakiness.
            robot_objects = []
            for _ in range(20):
                robot_objects = ctx.db_client.list(api_objects.RobotObjectV1)
                if len(robot_objects) > 0:
                    break
                time.sleep(0.1)

            if len(robot_objects) > 0:
                # Robot still present with PENDING_DELETE before controller hard-deletes
                self.assertEqual(
                    robot_objects[0].lifecycle,
                    api_objects.object.ObjectLifecycleV1.PENDING_DELETE)

            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                # mission should be set to failed once the robot is pending delete / deleted
                if update.status.state.done:
                    self.assertEqual(update.status.state,
                                     mission_object.MissionStateV1.FAILED)
                    break
            time.sleep(1)

            # The mission is finished, so the robot should be deleted
            robot_objects = ctx.db_client.list(api_objects.RobotObjectV1)
            self.assertEqual(len(robot_objects), 0)


if __name__ == "__main__":
    unittest.main()
