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
from packages.controllers.mission.tests import mission_examples

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


class TestMissions(unittest.TestCase):
    def test_long_mission(self):
        """ Test sending a very long mission to a single robot """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", mission_examples.MISSION_TREE_LONG))

            # Make sure the mission is updated and completed
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    break

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            waypoint = mission_examples.MISSION_TREE_LONG[-1]["route"]["waypoints"][-1]
            self.assertAlmostEqual(robot_status.pose.x,
                                   waypoint["x"], places=2)
            self.assertAlmostEqual(robot_status.pose.y,
                                   waypoint["y"], places=2)

    def test_single_mission(self):
        """ Test sending a single mission to a single robot """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "test01", SCENARIO1_WAYPOINTS))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO1_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            self.assertEqual(robot_status.pose.x, SCENARIO1_WAYPOINTS[-1][0])
            self.assertEqual(robot_status.pose.y, SCENARIO1_WAYPOINTS[-1][0])

    def test_robot_object_second(self):
        """ Test creating a mission for a robot that doesnt exist, then creating the robot later """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(test_context.mission_from_waypoints(
                "test01", SCENARIO1_WAYPOINTS))
            time.sleep(0.25)
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO1_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            self.assertEqual(robot_status.pose.x, SCENARIO1_WAYPOINTS[-1][0])
            self.assertEqual(robot_status.pose.y, SCENARIO1_WAYPOINTS[-1][0])

    def test_mission_failure(self):
        """ Test a sequence of 4 missions PASS, FAIL, PASS, FAIL """

        expected_states = [
            # All 4 missions start out as PENDING
            mission_object.MissionStatusV1(state="PENDING", current_node=0),
            mission_object.MissionStatusV1(state="PENDING", current_node=0),
            mission_object.MissionStatusV1(state="PENDING", current_node=0),
            mission_object.MissionStatusV1(state="PENDING", current_node=0),
            # The first mission runs then completes
            mission_object.MissionStatusV1(state="RUNNING", current_node=0),
            mission_object.MissionStatusV1(state="COMPLETED", current_node=0),
            # The second mission fails
            mission_object.MissionStatusV1(state="RUNNING", current_node=0),
            mission_object.MissionStatusV1(state="FAILED", current_node=0,
                                           failure_reason="Failure period reached"),
            # The third mission runs then completes
            mission_object.MissionStatusV1(state="RUNNING", current_node=0),
            mission_object.MissionStatusV1(state="COMPLETED", current_node=0),
            # The fourth mission fails
            mission_object.MissionStatusV1(state="RUNNING", current_node=0),
            mission_object.MissionStatusV1(state="FAILED", current_node=0,
                                           failure_reason="Failure period reached"),
        ]

        robot = simulator.RobotInit("test01", 0, 0, 0, "map", 2)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the four missions
            watcher = ctx.db_client.watch(api_objects.MissionObjectV1)
            for i in range(0, 4):
                mission = test_context.mission_from_waypoint(
                    "test01", i * 2 + 1, i * 2 + 1, "mission_" + str(i))
                ctx.db_client.create(mission)

            # Sequence matters, otherwise we can't capture the first mission's pending state
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(expected_states, watcher):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)

    def test_timeout(self):
        """ Test sending a mission that times out """
        MISSION_WAYPOINT_X = 15
        MISSION_WAYPOINT_Y = 15
        expected_statuses = [
            mission_object.MissionStatusV1(state="PENDING"),
            mission_object.MissionStatusV1(state="RUNNING"),
            mission_object.MissionStatusV1(state="FAILED",
                                           failure_reason="Mission timed out"),
        ]
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            watcher = ctx.db_client.watch(api_objects.MissionObjectV1)
            mission = test_context.mission_from_waypoint(
                "test01", MISSION_WAYPOINT_X, MISSION_WAYPOINT_Y)
            mission.timeout = 1
            ctx.db_client.create(mission)

            # Make sure the mission is listed as FAILED
            for expected_status, update in zip(expected_statuses, watcher):
                self.assertEqual(update.status.state, expected_status.state)
                if update.status.state == mission_object.MissionStateV1.FAILED:
                    self.assertEqual(update.status.failure_reason,
                                     expected_status.failure_reason)


if __name__ == "__main__":
    unittest.main()
