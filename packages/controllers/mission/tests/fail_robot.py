"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
import uuid

from cloud_common import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from cloud_common.objects import mission as mission_object
from cloud_common.objects import robot as robot_object

from packages.controllers.mission.tests import test_context

# Waypoint for a mission that will be reused for many tests
DEFAULT_MISSION_X = 10.0
DEFAULT_MISSION_Y = 10.0

# Definition for mission `SCENARIO1` with multiple waypoints
SCENARIO1_WAYPOINTS = [
    (1, 1),
    (10, 10),
    (5, 5),
]

# Expected progression of mission state for the mission `SCENARIO1`
SCENARIO1_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=1),
    mission_object.MissionStatusV1(state="RUNNING", current_node=2),
    mission_object.MissionStatusV1(state="COMPLETED", current_node=2),
]

SCENARIO2_WAYPOINTS = [
    (1, 1),
    (10, 10),
    (5, 5),
]

SCENARIO2_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="FAILED", current_node=0),
]


class TestMissions(unittest.TestCase):
    def test_warning_mission(self):
        """ Test sending a single mission to a single robot that always is a warning """
        robot = simulator.RobotInit("warning_robot01", 0, 0, 0, "map", 1)
        with test_context.TestContext([robot], fail_as_warning=True) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(api_objects.RobotObjectV1(
                name="warning_robot01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "warning_robot01", SCENARIO1_WAYPOINTS))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO1_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "warning_robot01").status
            self.assertEqual(robot_status.pose.x, SCENARIO1_WAYPOINTS[-1][0])
            self.assertEqual(robot_status.pose.y, SCENARIO1_WAYPOINTS[-1][0])

    def test_fatal_mission(self):
        """ Test a single mission to a single robot that always is fatal """
        robot = simulator.RobotInit("fatal_robot01", 0, 0, 0, "map", 1)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(api_objects.RobotObjectV1(
                name="fatal_robot01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "fatal_robot01", SCENARIO2_WAYPOINTS))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO2_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)


if __name__ == "__main__":
    unittest.main()
