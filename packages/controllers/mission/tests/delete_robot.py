"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

from packages import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from packages.objects import mission as mission_object
from packages.objects import robot as robot_object

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

            # Delete robot
            ctx.db_client.delete(api_objects.RobotObjectV1, "test01")
            time.sleep(10)

            # Check to see if the robot is gone from the database
            self.assertEqual(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

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
            time.sleep(0.25)
            robot_objects = ctx.db_client.list(api_objects.RobotObjectV1)

            # Robot should not be deleted yet, mission should still be ongoing and therefore robot is still
            # on task.
            self.assertGreater(len(robot_objects), 0)
            self.assertEqual(
                robot_objects[0].lifecycle, api_objects.object.ObjectLifecycleV1.PENDING_DELETE)
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    break
            time.sleep(1)

            # The mission is finished, so the robot should be deleted
            robot_objects = ctx.db_client.list(api_objects.RobotObjectV1)
            self.assertEqual(len(robot_objects), 0)


if __name__ == "__main__":
    unittest.main()
