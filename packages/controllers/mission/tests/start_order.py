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
from cloud_common.objects import robot as robot_object

from packages.controllers.mission.tests import test_context


class TestMissions(unittest.TestCase):
    def run_single_mission(self, ctx: test_context.TestContext):
        """ Helper function to run a simple mission on a single robot """

        # Waypoint for a scenario that will be reused for different test cases
        MISSION_WAYPOINT_X = 30.0
        MISSION_WAYPOINT_Y = 30.0

        # Create the robot and then the mission
        ctx.db_client.create(
            api_objects.RobotObjectV1(name="test01", status={}))
        time.sleep(0.25)
        ctx.db_client.create(test_context.mission_from_waypoint(
            "test01", MISSION_WAYPOINT_X, MISSION_WAYPOINT_Y))
        time.sleep(0.25)

        # Make sure the mission is done.
        # The result can be either completed or failed based on state of robot client
        completed = False
        for update in ctx.db_client.watch(api_objects.MissionObjectV1):
            if update.status.state.done:
                completed = True
                break
        self.assertTrue(completed)

    def test_mission_dispatch_slow(self):
        """ Test the case where the mission dispatch starts last """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        delay = test_context.Delay(mission_dispatch=10)
        with test_context.TestContext([robot], delay=delay, enforce_start_order=False) as ctx:
            ctx.wait_for_database()
            self.run_single_mission(ctx)

    def test_mission_simulator_slow(self):
        """ Test the case where the mission simulator starts last """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        delay = test_context.Delay(mission_simulator=10)
        with test_context.TestContext([robot], delay=delay, enforce_start_order=False) as ctx:
            ctx.wait_for_database()
            self.run_single_mission(ctx)

    def test_mqtt_broker_slow(self):
        """ Test the case where the mqtt broker starts last """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        delay = test_context.Delay(mqtt_broker=10)
        with test_context.TestContext([robot], delay=delay, enforce_start_order=False) as ctx:
            ctx.wait_for_database()
            self.run_single_mission(ctx)

    def test_mission_database_slow(self):
        """ Test the case where the mission database starts last """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        delay = test_context.Delay(mission_database=10)
        with test_context.TestContext([robot], delay=delay, enforce_start_order=False) as ctx:
            ctx.wait_for_database()
            self.run_single_mission(ctx)


if __name__ == "__main__":
    unittest.main()
