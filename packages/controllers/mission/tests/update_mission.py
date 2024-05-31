"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
from cloud_common.objects import common

from packages.controllers.mission.tests import test_context

WAYPOINT_1 = (10, 10)
WAYPOINT_2 = (5, 5)
WAYPOINT_3 = (3, 3)

MISSION_TREE = [
    test_context.route_generator(),
    {"name": "selector_1", "selector": {}, "parent": "root"},
    test_context.action_generator(params={"should_fail": 1, "time": 3}, parent="selector_1"),
    {"name": "sequence_1", "sequence": {}, "parent": "selector_1"},
    test_context.route_generator(parent="sequence_1"),
    test_context.route_generator(parent="sequence_1"),
    test_context.route_generator()
]


class TestUpdateMissions(unittest.TestCase):
    def test_update_pending_mission(self):
        """ Test if pending mission gets updated """

        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create two missions
            mission_1 = test_context.mission_from_waypoint(
                "test01", WAYPOINT_1[0], WAYPOINT_1[1])
            ctx.db_client.create(mission_1)
            time.sleep(0.25)

            # The second mission will be pending as the robot executes the first mission.
            mission_2 = test_context.mission_from_waypoint(
                "test01", WAYPOINT_2[0], WAYPOINT_2[1])
            ctx.db_client.create(mission_2)

            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)

            # Update the second mission
            update_nodes = {"0": {"waypoints": [
                {"x": WAYPOINT_3[0], "y": WAYPOINT_3[1], "theta": 0}]}}
            ctx.db_client.update_mission(mission_2.name, update_nodes)

            # Wait till it's done
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done and mission.name == mission_2.name:
                    self.assertEqual(mission.status.state,
                                     mission_object.MissionStateV1.COMPLETED)
                    break

            # Make sure the robot is at the updated position
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            self.assertAlmostEqual(robot_status.pose.x,
                                   WAYPOINT_3[0], places=2)
            self.assertAlmostEqual(robot_status.pose.y,
                                   WAYPOINT_3[1], places=2)

    def test_update_running_mission(self):
        """ Test if running mission gets updated """

        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create a mission
            mission_1 = test_context.mission_object_generator(
                "test01", MISSION_TREE)
            ctx.db_client.create(mission_1)
            time.sleep(0.25)

            # Update node 6
            update_nodes = {"6": {"waypoints": [
                {"x": WAYPOINT_2[0], "y": WAYPOINT_2[1], "theta": 0}]}}
            ctx.db_client.update_mission(mission_1.name, update_nodes)

            # Wait till it's done
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done and mission.name == mission_1.name:
                    self.assertEqual(mission.status.state,
                                     mission_object.MissionStateV1.COMPLETED)
                    break

            # Make sure the robot is at the updated position
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            self.assertAlmostEqual(robot_status.pose.x,
                                   WAYPOINT_2[0], places=2)
            self.assertAlmostEqual(robot_status.pose.y,
                                   WAYPOINT_2[1], places=2)

    def test_update_completed_mission(self):
        """ Test if completed mission gets updated """

        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create a mission
            mission_1 = test_context.mission_from_waypoint(
                "test01", WAYPOINT_3[0], WAYPOINT_3[1])
            ctx.db_client.create(mission_1)
            time.sleep(0.25)

            # Wait till it's done
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done and mission.name == mission_1.name:
                    self.assertEqual(mission.status.state,
                                     mission_object.MissionStateV1.COMPLETED)
                    break

            # Update a completed mission
            update_nodes = {"0": {"waypoints": [
                {"x": WAYPOINT_1[0], "y": WAYPOINT_1[1], "theta": 0}]}}
            with self.assertRaises(common.ICSUsageError):
                ctx.db_client.update_mission(mission_1.name, update_nodes)


if __name__ == "__main__":
    unittest.main()
