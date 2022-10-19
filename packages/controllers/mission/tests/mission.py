"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

from packages import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from packages.objects import mission as mission_object
from packages.objects import robot as robot_object

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

class TestMissions(unittest.TestCase):
    def test_single_mission(self):
        """ Test sending a single mission to a single robot """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints("test01", SCENARIO1_WAYPOINTS))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO1_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node, expected_state.current_node)

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(api_objects.RobotObjectV1, "test01").status
            self.assertEqual(robot_status.pose.x, SCENARIO1_WAYPOINTS[-1][0])
            self.assertEqual(robot_status.pose.y, SCENARIO1_WAYPOINTS[-1][0])

    def test_robot_object_second(self):
        """ Test creating a mission for a robot that doesnt exist, then creating the robot later """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(test_context.mission_from_waypoints("test01", SCENARIO1_WAYPOINTS))
            time.sleep(0.25)
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO1_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node, expected_state.current_node)

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(api_objects.RobotObjectV1, "test01").status
            self.assertEqual(robot_status.pose.x, SCENARIO1_WAYPOINTS[-1][0])
            self.assertEqual(robot_status.pose.y, SCENARIO1_WAYPOINTS[-1][0])

    def test_many_robots(self):
        """ Test sending a mission to 5 different robots at the same time """
        sim_robots = []
        robots = []
        missions = []
        num_robots = 5

        for i in range(0, num_robots):
            name = f"test{i:02d}"
            sim_robots.append(simulator.RobotInit(name, i, i))
            robots.append(api_objects.RobotObjectV1(name=name, status={}))
            missions.append(test_context.mission_from_waypoint(name, i + 10, i + 5))

        with test_context.TestContext(sim_robots) as ctx:
            for robot in robots:
                ctx.db_client.create(robot)
            for mission in missions:
                ctx.db_client.create(mission)

            # Wait for all missions to complete
            completed_missions = set()
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.COMPLETED:
                    completed_missions.add(mission.name)
                if len(completed_missions) == len(missions):
                    break
            time.sleep(1)

            # Check the state of all missions and robots
            db_robots = ctx.db_client.list(api_objects.RobotObjectV1)
            db_missions = ctx.db_client.list(api_objects.MissionObjectV1)

            for mission in db_missions:
                self.assertEqual(mission.status.state, mission_object.MissionStateV1.COMPLETED)
            for robot in db_robots:
                id = int(robot.name.lstrip("test"))
                self.assertEqual(robot.status.pose.x, id + 10)
                self.assertEqual(robot.status.pose.y, id + 5)

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

        robot = simulator.RobotInit("test01", 0, 0, 0, 2)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the four missions
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            for i in range(0, 4):
                ctx.db_client.create(test_context.mission_from_waypoint("test01", i + 1, i + 1))

            # Make sure the mission is updated and completed
            for expected_state, update in zip(expected_states,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node, expected_state.current_node)

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
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            mission = test_context.mission_from_waypoint("test01", MISSION_WAYPOINT_X, MISSION_WAYPOINT_Y)
            mission.timeout = 1
            ctx.db_client.create(mission)

            # Make sure the mission is listed as FAILED
            for expected_status, update in zip(expected_statuses,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_status.state)
                if update.status.state == mission_object.MissionStateV1.FAILED:
                    self.assertEqual(update.status.failure_reason, expected_status.failure_reason)
    
    def test_robot_offline(self):
        """ Test that the server labels the robot as offline after not receiving messages """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=2.0) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", heartbeat_timeout=1, status={}))

            # The simulator "tick_period" is smaller than the heartbeat_timeout, so the robot
            # will alternate between online and offline
            expected_online = [False, True, False, True]
            for online, update in zip(expected_online,
                                      ctx.db_client.watch(api_objects.RobotObjectV1)):
                self.assertEqual(update.status.online, online)

    def test_robot_task_state(self):
        """ Test if the robot task state is correctly updated """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))

            # Create a watcher so we can see how the state of the robot changes over time
            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)

            # Submit a mission to the robot
            ctx.db_client.create(test_context.mission_from_waypoint("test01",
                                                                    DEFAULT_MISSION_X, DEFAULT_MISSION_Y))

            # Grab the first state, the robot should be IDLE
            first_update = next(watcher)
            self.assertEqual(first_update.status.state, robot_object.RobotStateV1.IDLE)

            # Wait for the robot to be ON_TASK
            for update in watcher:
                if update.status.state == robot_object.RobotStateV1.ON_TASK:
                    break

            # Wait for the robot to be IDLE and verify its in the right place
            for update in watcher:
                if update.status.state == robot_object.RobotStateV1.IDLE:
                    self.assertEqual(update.status.pose.x, DEFAULT_MISSION_X)
                    self.assertEqual(update.status.pose.y, DEFAULT_MISSION_Y)
                    break

    def test_robot_hardware_version_update(self):
        """ Test robot hardware version update """
        robot = simulator.RobotInit("test01", 0, 0, 0, 0, "NV", "1NV023200CAR00010")
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints("test01", SCENARIO1_WAYPOINTS))

            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)
            for update in watcher:
                if update.status.online:
                    break
            next_update = next(watcher)

            robot_hardware = next_update.status.hardware_version
            self.assertEqual(robot_hardware.manufacturer, "NV")
            self.assertEqual(robot_hardware.serial_number, "1NV023200CAR00010")
   
if __name__ == "__main__":
    unittest.main()
