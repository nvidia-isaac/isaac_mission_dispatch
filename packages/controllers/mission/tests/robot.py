"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2022-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
import datetime
import time
import unittest
import paho.mqtt.client as mqtt_client
import packages.controllers.mission.vda5050_types as types

from cloud_common import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from cloud_common.objects import mission as mission_object
from cloud_common.objects import robot as robot_object
from cloud_common.objects.robot import RobotStateV1

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

MISSION_TREE_1 = [
    test_context.route_generator(),
    test_context.action_generator(
        params={}, name="teleop", action_type="pause_order"),
    test_context.route_generator()
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

    def test_charging_transition(self):
        """ Validate charging state transition """
        robot = simulator.RobotInit("test01", 0, 0)
        # Create MQTT Client to simulate messages from robot
        client = mqtt_client.Client(transport=test_context.MQTT_TRANSPORT)
        client.ws_set_options(path=test_context.MQTT_WS_PATH)
        with test_context.TestContext([robot]) as ctx:
            client.connect(ctx.mqtt_address, test_context.MQTT_PORT)
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))

            # Initial state is IDLE
            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)
            for update in watcher:
                if update.status.state == RobotStateV1.IDLE:
                    break

            # Publish charging=True message
            # State should transition to CHARGING
            topic = f"{test_context.MQTT_PREFIX}/test01/state"
            message = types.VDA5050OrderInformation(
                headerId=0,
                timestamp=datetime.datetime.now().isoformat(),
                manufacturer="",
                serialNumber="",
                orderId="",
                orderUpdateId=0,
                lastNodeId="",
                lastNodeSequenceId=0,
                nodeStates=[],
                edgeStates=[],
                actionStates=[],
                agvPosition={"x": 0, "y": 0,
                            "theta": 0, "mapId": ""},
                batteryState={"batteryCharge": 50,
                            "charging": True})
            client.publish(topic, message.json())
            time.sleep(0.5)
            for update in watcher:
                if update.status.state == RobotStateV1.CHARGING:
                    break

            # Publish charging=False message
            # State should transition to IDLE
            message.batteryState.charging = False
            client.publish(topic, message.json())
            time.sleep(0.5)
            for update in watcher:
                if update.status.state == RobotStateV1.IDLE:
                    break

    def test_teleop_in_mission(self):
        """ Test mission with teleop node"""
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_1))

            # Make sure the robot is in teleop mode
            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)
            for update in watcher:
                if update.status.state == robot_object.RobotStateV1.TELEOP:
                    break
            # Simulate teleop
            time.sleep(5)
            # Stop teleop
            ctx.call_teleop_service(robot_name="test01", teleop=robot_object.RobotTeleopActionV1.STOP)
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    break

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            waypoint = MISSION_TREE_1[-1]["route"]["waypoints"][-1]
            self.assertAlmostEqual(robot_status.pose.x,
                                   waypoint["x"], places=2)
            self.assertAlmostEqual(robot_status.pose.y,
                                   waypoint["y"], places=2)

    def test_teleop_by_user_request(self):
        """ Test teleop by user request"""
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "test01", SCENARIO1_WAYPOINTS))

            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.RUNNING:
                    break
            # Simulate teleop
            watcher = ctx.db_client.watch(api_objects.RobotObjectV1)
            # Start teleop
            ctx.call_teleop_service(robot_name="test01", teleop=robot_object.RobotTeleopActionV1.START)
            time.sleep(5)
            for update in watcher:
                if update.status.state == robot_object.RobotStateV1.TELEOP:
                    break
            # Stop teleop
            ctx.call_teleop_service(robot_name="test01", teleop=robot_object.RobotTeleopActionV1.STOP)
            for update in watcher:
                if update.status.state == robot_object.RobotStateV1.ON_TASK:
                    break
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    break


if __name__ == "__main__":
    unittest.main()
