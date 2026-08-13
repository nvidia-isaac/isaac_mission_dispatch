"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
import math

from cloud_common import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from cloud_common.objects import mission as mission_object
from cloud_common.objects import robot as robot_object
from cloud_common.objects.robot import VDA5050AgvClass
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


class TestVDA5050Compatibility(unittest.TestCase):
    def test_long_mission(self):
        """ Test sending a very long mission to a single robot """
        robot = simulator.RobotInit("test01", 0, 0, 0, vda5050_version="3.0.0", battery=100.0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(test_context.mission_from_waypoints(
                "test01", SCENARIO1_WAYPOINTS))

            # Make sure the mission is updated and completed
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    break

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            self.assertEqual(robot_status.pose.x, SCENARIO1_WAYPOINTS[-1][0])
            self.assertEqual(robot_status.pose.y, SCENARIO1_WAYPOINTS[-1][0])

            # Make sure the battery level is readable
            self.assertAlmostEqual(robot_status.battery_level, 100.0, places=2)

    def test_retrieve_factsheet(self):
        """ Test if factsheet retrieval and instant actions in vda5050 3.0.0 is functional """

        robot_arm = simulator.RobotInit(
            "test01", 0, 0, 0, robot_type=VDA5050AgvClass.MANIPULATOR, vda5050_version="3.0.0")
        robot_amr = simulator.RobotInit(
            "test02", 0, 0, 0, robot_type=VDA5050AgvClass.CARRIER, vda5050_version="3.0.0")
        with test_context.TestContext([robot_arm, robot_amr], tick_period=1.0) as ctx:
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            start_time = time.time()
            while time.time() - start_time < 120:
                factsheet = ctx.db_client.get(robot_object.RobotObjectV1, "test01").status.factsheet
                if factsheet.agv_class == VDA5050AgvClass.MANIPULATOR.value:
                    break
                time.sleep(0.50)
            assert (factsheet.agv_class == VDA5050AgvClass.MANIPULATOR.value)

            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test02", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 1)

            start_time = time.time()
            while time.time() - start_time < 120:
                factsheet = ctx.db_client.get(robot_object.RobotObjectV1, "test02").status.factsheet
                if factsheet.agv_class == VDA5050AgvClass.CARRIER.value:
                    break
                time.sleep(0.50)
            assert (factsheet.agv_class == VDA5050AgvClass.CARRIER.value)


if __name__ == "__main__":
    unittest.main()
