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
import types
import unittest
from unittest import mock

from cloud_common import objects as api_objects
from cloud_common.objects import robot as robot_object
from packages.controllers.mission import server as mission_server
from packages.controllers.mission.tests import client as simulator
from cloud_common.objects import mission as mission_object
from packages.controllers.mission.tests import test_context

# Definition for mission `SCENARIO1` with multiple waypoints
SCENARIO1_WAYPOINTS = [
    (1, 1),
    (5, 5),
]

# Expected progression of mission state for the mission `SCENARIO1`
SCENARIO1_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=1),
    mission_object.MissionStatusV1(state="COMPLETED", current_node=1),
]


class TestMissionServer(unittest.TestCase):
    def test_client_update_freq(self):
        """ Test a mission with different update frequencies of the client simulator """
        tick_periods = [1, 0.1, 0.01]
        for tick_period in tick_periods:
            robot = simulator.RobotInit("test01", 0, 0, 0)
            with test_context.TestContext([robot], tick_period=tick_period) as ctx:
                # Create the robot and then the mission
                ctx.db_client.create(
                    api_objects.RobotObjectV1(name="test01", status={}))
                time.sleep(0.25)
                ctx.db_client.create(test_context.mission_from_waypoints("test01",
                                                                         SCENARIO1_WAYPOINTS))

                # Make sure the mission is updated and completed
                for expected_state, update in zip(SCENARIO1_EXPECTED_STATUSES,
                                                  ctx.db_client.watch(api_objects.MissionObjectV1)):
                    self.assertEqual(update.status.state, expected_state.state)
                    self.assertEqual(update.status.current_node,
                                     expected_state.current_node)

    def test_restart_from_database(self):
        """ Test if MD can restart from the database """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        restart_once = False
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "test01", SCENARIO1_WAYPOINTS))

            # Make sure the mission is updated and completed
            completed = False
            watcher = ctx.db_client.watch(api_objects.MissionObjectV1)
            for update in watcher:
                if not restart_once and update.status.state == "RUNNING":
                    ctx.restart_mission_server()
                    print("Restart mission server")
                    restart_once = True
                    continue
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    completed = True
                    break
            self.assertTrue(completed)

    def test_mqtt_reconnection(self):
        """ Test if MD is able to handle MQTT reconnection """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        restart_once = False
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "test01", SCENARIO1_WAYPOINTS))

            # Make sure the mission is updated and completed
            completed = False
            watcher = ctx.db_client.watch(api_objects.MissionObjectV1)
            for update in watcher:
                if not restart_once and update.status.state == "RUNNING":
                    ctx.restart_mqtt_server()
                    print("Restart the Mosquitto broker")
                    restart_once = True
                    continue
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    completed = True
                    break
            self.assertTrue(completed)


class TestRobotStateUpdates(unittest.TestCase):

    def setUp(self):
        self.robot = mission_server.Robot.__new__(mission_server.Robot)
        self.robot._current_mission = mock.sentinel.mission
        self.robot._set_robot_state = mock.Mock()
        self.robot.mission_info = mock.Mock()

    @staticmethod
    def action(action_type):
        return types.SimpleNamespace(actionType=action_type)

    def test_non_teleop_action_does_not_change_robot_state(self):
        self.robot.update_robot_state([
            self.action(
                mission_server.types.VDA5050InstantActionType.FACTSHEET_REQUEST)
        ])

        self.robot._set_robot_state.assert_not_called()
        self.robot.mission_info.assert_not_called()

    def test_teleop_actions_change_robot_state(self):
        actions = [
            self.action(
                mission_server.types.VDA5050InstantActionType.FACTSHEET_REQUEST),
            self.action(mission_server.types.NVInstantActionType.START_TELEOP),
        ]
        self.robot.update_robot_state(actions)
        self.robot._set_robot_state.assert_called_once_with(
            robot_object.RobotStateV1.TELEOP)

        self.robot._set_robot_state.reset_mock()
        self.robot.update_robot_state([
            self.action(mission_server.types.NVInstantActionType.STOP_TELEOP)
        ])
        self.robot._set_robot_state.assert_called_once_with(
            robot_object.RobotStateV1.ON_TASK)


class TestMqttPayloadValidation(unittest.TestCase):

    def setUp(self):
        self.robot_server = mission_server.RobotServer.__new__(
            mission_server.RobotServer)
        self.robot_server._mqtt_prefix = "uagv/v2/RobotCompany"
        self.robot_server._mqtt_messages = mock.sentinel.message_queue
        self.robot_server._enqueue = mock.Mock()
        self.robot_server.info = mock.Mock()
        self.robot_server.warning = mock.Mock()

    def test_malformed_payloads_are_rejected_without_enqueueing(self):
        topic = "uagv/v2/RobotCompany/robot/state"

        for payload in (b'{"truncated"', b'\xff'):
            with self.subTest(payload=payload):
                message = types.SimpleNamespace(topic=topic, payload=payload)
                self.robot_server._mqtt_on_message(None, None, message)

        self.assertEqual(self.robot_server.warning.call_count, 2)
        self.robot_server._enqueue.assert_not_called()

    @mock.patch.object(mission_server.mqtt_client.Client, "connect")
    def test_mqtt_client_suppresses_callback_exceptions(self, connect):
        callback = mock.Mock(side_effect=RuntimeError("callback failed"))
        self.robot_server._mqtt_on_message = callback
        connected_client = self.robot_server._connect_to_mqtt(
            "localhost", 1883, "tcp", None, None, None)

        message = types.SimpleNamespace(topic="robot/state")
        connected_client._handle_on_message(message)

        connect.assert_called_once_with("localhost", 1883)
        callback.assert_called_once_with(connected_client, None, message)


if __name__ == "__main__":
    unittest.main()
