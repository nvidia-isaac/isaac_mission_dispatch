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

from packages import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from packages.objects import mission as mission_object
from packages.objects import robot as robot_object

from packages.controllers.mission.tests import test_context

class TestCancelMissions(unittest.TestCase):
    def test_cancel_pending_mission(self):
        """ Test if pending mission gets canceled """
        waypoints_1 = (10, 10)
        waypoints_2 = (3, 3)
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            self.assertGreater(len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create two missions
            mission_1 = test_context.mission_from_waypoint("test01", waypoints_1[0], waypoints_1[1])
            ctx.db_client.create(mission_1)

            # The second mission will be pending as the robot executes the first mission.
            # The test will demonstrate the cancelation of this pending mission.
            mission_2 = test_context.mission_from_waypoint("test01", waypoints_2[0], waypoints_2[1])
            ctx.db_client.create(mission_2)

            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)

            # Cancel the mission
            ctx.db_client.cancel_mission(mission_2.name)
            #time.sleep(0.25)
            time.sleep(1.0)

            # Check that the second mission has been canceled
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)
            self.assertEqual(missions[1].status.state, mission_object.MissionStateV1.CANCELED)

    def test_delete_pending_mission(self):
        """ Test if pending mission gets deleted """
        waypoints_1 = (10, 10)
        waypoints_2 = (3, 3)
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            self.assertGreater(len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create two missions
            mission_1 = test_context.mission_from_waypoint("test01", waypoints_1[0], waypoints_1[1])
            ctx.db_client.create(mission_1)

            # The second mission will be pending as the robot executes the first mission.
            # The test will demonstrate the cancelation of this pending mission.
            mission_2 = test_context.mission_from_waypoint("test01", waypoints_2[0], waypoints_2[1])
            ctx.db_client.create(mission_2)

            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)

            # Delete the mission
            ctx.db_client.delete(api_objects.MissionObjectV1, mission_2.name)
            time.sleep(0.25)

            # Check that the second mission has been deleted
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 1)

    def test_cancel_running_mission(self):
        """ Test if running mission gets canceled """
        waypoint_x = 5
        waypoint_y = 5
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create mission. This is a long mission so that the cancelation request is made
            # while the mission is still running.
            test_mission = test_context.mission_from_waypoint("test01", waypoint_x, waypoint_y)
            ctx.db_client.create(test_mission)

            # Make sure the mission is running
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.RUNNING:
                    break

            # Cancel the mission
            ctx.db_client.cancel_mission(test_mission.name)
            time.sleep(0.5)

            # Wait till it completes
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.COMPLETED:
                    break

            # Check that the mission has been canceled
            time.sleep(0.25)
            next_update = next(ctx.db_client.watch(api_objects.MissionObjectV1))
            self.assertEqual(next_update.status.state, mission_object.MissionStateV1.CANCELED)
            self.assertEqual(len(ctx.db_client.list(api_objects.MissionObjectV1)), 1)

    def test_delete_running_mission(self):
        """ Test if running mission gets deleted after completed """
        waypoint_x = 5
        waypoint_y = 5
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)

            # Create mission. This is a long mission so that the cancelation request is made
            # while the mission is still running.
            test_mission = test_context.mission_from_waypoint("test01", waypoint_x, waypoint_y)
            ctx.db_client.create(test_mission)

            # Make sure the mission is running
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.RUNNING:
                    break

            # Delete the mission
            ctx.db_client.delete(api_objects.MissionObjectV1, test_mission.name)
            time.sleep(0.25)
            fetched_mission = ctx.db_client.get(api_objects.MissionObjectV1, test_mission.name)
            self.assertEqual(fetched_mission.lifecycle, api_objects.object.ObjectLifecycleV1.PENDING_DELETE)
            self.assertEqual(len(ctx.db_client.list(api_objects.MissionObjectV1)), 1)

            # Wait the mission is completed
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    break

            # Check that the mission has been deleted
            time.sleep(0.25)
            self.assertEqual(len(ctx.db_client.list(api_objects.MissionObjectV1)), 0)

    def test_skip_canceled_mission(self):
        """ Test if a mission after a canceled mission gets properly executed """
        waypoints = [(5, 5), (5, 10), (10, 5)]
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create the missions
            missions = []
            for waypoint in waypoints:
                mission = test_context.mission_from_waypoint("test01", waypoint[0], waypoint[1])
                missions.append(mission)
                ctx.db_client.create(mission)

            # Cancel the second mission
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 3)
            mission_to_cancel = missions[1].name
            last_mission_name = missions[2].name
            ctx.db_client.cancel_mission(mission_to_cancel)
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.COMPLETED and \
                    mission.name == last_mission_name:
                    break

            # Check that the second mission has been canceled, and the mission after is completed
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 3)
            for mission in missions:
                expected_state = mission_object.MissionStateV1.COMPLETED
                if mission.name == mission_to_cancel:
                    expected_state = mission_object.MissionStateV1.CANCELED
            self.assertEqual(mission.status.state, expected_state)

    def test_cancel_running_mission_run_new_mission(self):
        """ Test if canceling a running mission will transition to running a new mission """
        waypoints = [(10, 10), (3, 3)]
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=0.5) as ctx:
            # Create the robot
            ctx.db_client.create(api_objects.RobotObjectV1(name="test01", status={}))
            self.assertGreater(len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create the missions
            for waypoint in waypoints:
                mission = test_context.mission_from_waypoint("test01", waypoint[0], waypoint[1])
                ctx.db_client.create(mission)

            # Cancel the first mission
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)
            mission_to_cancel = missions[0].name
            last_mission_name = missions[1].name
            ctx.db_client.cancel_mission(mission_to_cancel)
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.COMPLETED and \
                    mission.name == last_mission_name:
                    break

            # Check that the first mission has been canceled, and the mission after is completed
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)
            self.assertEqual(missions[0].status.state, mission_object.MissionStateV1.CANCELED)
            self.assertEqual(missions[1].status.state, mission_object.MissionStateV1.COMPLETED)

if __name__ == "__main__":
    unittest.main()
