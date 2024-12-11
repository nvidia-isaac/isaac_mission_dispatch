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
from cloud_common.objects import common

from packages.controllers.mission.tests import test_context


class TestCancelMissions(unittest.TestCase):
    def test_cancel_pending_mission(self):
        """ Test if pending mission gets canceled """
        waypoints_1 = (10, 10)
        waypoints_2 = (3, 3)
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create two missions
            mission_1 = test_context.mission_from_waypoint(
                "test01", waypoints_1[0], waypoints_1[1])
            ctx.db_client.create(mission_1)
            time.sleep(0.25)

            # The second mission will be pending as the robot executes the first mission.
            # The test will demonstrate the cancelation of this pending mission.
            mission_2 = test_context.mission_from_waypoint(
                "test01", waypoints_2[0], waypoints_2[1])
            ctx.db_client.create(mission_2)

            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)

            # Cancel the mission
            ctx.db_client.cancel_mission(mission_2.name)
            # Wait till it's done
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done and mission.name == mission_2.name:
                    self.assertEqual(mission.status.state,
                                     mission_object.MissionStateV1.CANCELED)
                    break

    def test_delete_pending_mission(self):
        """ Test if pending mission gets deleted """
        waypoints_1 = (10, 10)
        waypoints_2 = (3, 3)
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create two missions
            mission_1 = test_context.mission_from_waypoint(
                "test01", waypoints_1[0], waypoints_1[1])
            ctx.db_client.create(mission_1)
            time.sleep(0.25)

            # The second mission will be pending as the robot executes the first mission.
            # The test will demonstrate the cancelation of this pending mission.
            mission_2 = test_context.mission_from_waypoint(
                "test01", waypoints_2[0], waypoints_2[1])
            ctx.db_client.create(mission_2)

            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)

            # Delete the mission
            ctx.db_client.delete(api_objects.MissionObjectV1, mission_2.name)
            time.sleep(10)

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
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create mission. This is a long mission so that the cancelation request is made
            # while the mission is still running.
            test_mission = test_context.mission_from_waypoint(
                "test01", waypoint_x, waypoint_y)
            ctx.db_client.create(test_mission)

            # Make sure the mission is running
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.RUNNING:
                    break

            # Cancel the mission
            ctx.db_client.cancel_mission(test_mission.name)

            # Wait till it's done
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done:
                    self.assertEqual(mission.status.state,
                                     mission_object.MissionStateV1.CANCELED)
                    self.assertEqual(
                        mission.status.node_status["0"].state, mission_object.MissionStateV1.CANCELED)
                    self.assertEqual(
                        len(ctx.db_client.list(api_objects.MissionObjectV1)), 1)
                    break

    def test_delete_running_mission(self):
        """ Test if running mission gets deleted after completed """
        waypoint_x = 5
        waypoint_y = 5
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=1.0) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)

            # Create mission. This is a long mission so that the cancelation request is made
            # while the mission is still running.
            test_mission = test_context.mission_from_waypoint(
                "test01", waypoint_x, waypoint_y)
            ctx.db_client.create(test_mission)

            # Make sure the mission is running
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.RUNNING and mission.name == test_mission.name:
                    break

            # Delete the mission
            ctx.db_client.delete(
                api_objects.MissionObjectV1, test_mission.name)
            time.sleep(0.25)
            fetched_mission = ctx.db_client.get(
                api_objects.MissionObjectV1, test_mission.name)
            self.assertEqual(fetched_mission.lifecycle,
                             api_objects.object.ObjectLifecycleV1.PENDING_DELETE)
            self.assertEqual(
                len(ctx.db_client.list(api_objects.MissionObjectV1)), 1)

            # Wait the mission is completed
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state.done:
                    break

            # Check that the mission has been deleted
            time.sleep(0.25)
            self.assertEqual(
                len(ctx.db_client.list(api_objects.MissionObjectV1)), 0)

    def test_skip_canceled_mission(self):
        """ Test if a mission after a canceled mission gets properly executed """
        waypoints = [(5, 5), (5, 10), (10, 5)]
        mission_names = ["m1", "m_cancel", "m3"]
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            for waypoint, name in zip(waypoints, mission_names):
                mission = test_context.mission_from_waypoint(
                    "test01", waypoint[0], waypoint[1], name)
                ctx.db_client.create(mission)
                # In case the mission is done before cancel
                if name == "m_cancel":
                    ctx.db_client.cancel_mission(name)

            # Cancel the second mission
            completed_mission = 0
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done:
                    completed_mission += 1
                    if completed_mission == 3:
                        break

            # Check that the second mission has been canceled, and the mission after is completed
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 3)
            for mission in missions:
                expected_state = mission_object.MissionStateV1.COMPLETED
                if mission.name == "m_cancel":
                    expected_state = mission_object.MissionStateV1.CANCELED
                self.assertEqual(mission.status.state, expected_state)

    def test_cancel_running_mission_run_new_mission(self):
        """ Test if canceling a running mission will transition to running a new mission """
        waypoints = [(10, 10), (3, 3)]
        mission_names = []
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot], tick_period=0.5) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create the missions
            for waypoint in waypoints:
                mission = test_context.mission_from_waypoint(
                    "test01", waypoint[0], waypoint[1])
                ctx.db_client.create(mission)
                mission_names.append(mission.name)
                time.sleep(0.25)

            # Make sure the mission is running
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state == mission_object.MissionStateV1.RUNNING and \
                        mission.name == mission_names[0]:
                    break

            # Cancel the first mission
            ctx.db_client.cancel_mission(mission_names[0])
            finished_mission = 0
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done:
                    finished_mission += 1
                    if finished_mission == 2:
                        break

            # Check that the first mission has been canceled, and the mission after is completed
            missions = ctx.db_client.list(api_objects.MissionObjectV1)
            self.assertEqual(len(missions), 2)
            idx = 0 if missions[0].name == mission_names[0] else 1
            self.assertEqual(missions[idx].status.state,
                             mission_object.MissionStateV1.CANCELED)
            self.assertEqual(missions[1 - idx].status.state,
                             mission_object.MissionStateV1.COMPLETED)

    def test_delete_completed_mission(self):
        """ Test if a completed mission gets deleted """
        waypoint_x = 1
        waypoint_y = 1
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)

            # Create mission. This is a long mission so that the cancelation request is made
            # while the mission is still running.
            test_mission = test_context.mission_from_waypoint(
                "test01", waypoint_x, waypoint_y)
            ctx.db_client.create(test_mission)

            # Make sure the mission is completed
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done and mission.name == test_mission.name:
                    break

            # Delete the mission
            ctx.db_client.delete(
                api_objects.MissionObjectV1, test_mission.name)
            # Check that the mission has been deleted
            time.sleep(0.25)
            self.assertEqual(
                len(ctx.db_client.list(api_objects.MissionObjectV1)), 0)

    def test_cancel_completed_mission(self):
        """ Test if a completed mission can be canceled """
        waypoint_x = 1
        waypoint_y = 1
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create mission
            test_mission = test_context.mission_from_waypoint(
                "test01", waypoint_x, waypoint_y)
            ctx.db_client.create(test_mission)

            # Make sure the mission is completed
            for mission in ctx.db_client.watch(api_objects.MissionObjectV1):
                if mission.status.state.done:
                    break

            # Cancel the mission
            with self.assertRaises(common.ICSUsageError):
                ctx.db_client.cancel_mission(test_mission.name)


if __name__ == "__main__":
    unittest.main()
