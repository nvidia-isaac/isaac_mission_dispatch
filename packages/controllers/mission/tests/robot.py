"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

# Waypoint for a mission that will be reused for many tests
DEFAULT_MISSION_X = 10.0
DEFAULT_MISSION_Y = 10.0

# Definition for mission `SCENARIO1` with multiple waypoints
SCENARIO1_WAYPOINTS = [
    (1, 1),
    (10, 10),
    (5, 5),
]


class TestMissions(unittest.TestCase):

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
            missions.append(
                test_context.mission_from_waypoint(name, i + 10, i + 5))

        with test_context.TestContext(sim_robots) as ctx:
            for robot in robots:
                ctx.db_client.create(robot)
                time.sleep(0.25)
            for mission in missions:
                ctx.db_client.create(mission)
                time.sleep(0.25)

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
                self.assertEqual(mission.status.state,
                                 mission_object.MissionStateV1.COMPLETED)
            for robot in db_robots:
                id = int(robot.name.lstrip("test"))
                self.assertEqual(robot.status.pose.x, id + 10)
                self.assertEqual(robot.status.pose.y, id + 5)

    def test_robot_offline(self):
        """ Test that the server labels the robot as offline after not receiving messages """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=2.0) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(api_objects.RobotObjectV1(
                name="test01", heartbeat_timeout=1, status={}))

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
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))

            # Create a watcher so we can see how the state of the robot changes over time
            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)

            # Grab the first state, the robot should be IDLE
            first_update = next(watcher)
            self.assertEqual(first_update.status.state,
                             robot_object.RobotStateV1.IDLE)

            # Submit a mission to the robot
            ctx.db_client.create(test_context.mission_from_waypoint("test01",
                                                                    DEFAULT_MISSION_X, DEFAULT_MISSION_Y))

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
        robot = simulator.RobotInit(
            "test01", 0, 0, 0, "map", 0, 0, "NV", "1NV023200CAR00010")
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "test01", SCENARIO1_WAYPOINTS))

            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)
            for update in watcher:
                if update.status.online:
                    break
            next_update = next(watcher)

            robot_hardware = next_update.status.hardware_version
            self.assertEqual(robot_hardware.manufacturer, "NV")
            self.assertEqual(robot_hardware.serial_number, "1NV023200CAR00010")

    def test_battery_level(self):
        """" Validate battery level """
        robot = simulator.RobotInit("test01", 0, 0, battery=42)
        with test_context.TestContext([robot]) as ctx:
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)
            for update in watcher:
                if update.status.battery_level == 42:
                    break


if __name__ == "__main__":
    unittest.main()
