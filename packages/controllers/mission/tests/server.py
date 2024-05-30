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

from cloud_common import objects as api_objects
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


if __name__ == "__main__":
    unittest.main()
