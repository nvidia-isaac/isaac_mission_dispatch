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
import pydantic

from cloud_common import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from cloud_common.objects import mission as mission_object
from packages.controllers.mission.tests import test_context
from cloud_common.objects import common

# Mission tree examples
MISSION_TREE_1 = [
    test_context.route_generator(),
    test_context.action_generator(params={"should_fail": 0, "time": 1}),
    test_context.action_generator(params={"should_fail": 0, "time": 2}),
    test_context.route_generator()
]
# Expected progression of mission state for the mission `MISSION_TREE_1`
SCENARIO1_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=1),
    mission_object.MissionStatusV1(state="RUNNING", current_node=2),
    mission_object.MissionStatusV1(state="RUNNING", current_node=3),
    mission_object.MissionStatusV1(state="COMPLETED", current_node=3,
                                   node_status={'root': {'state': 'COMPLETED'},
                                                '0': {'state': 'COMPLETED'},
                                                '1': {'state': 'COMPLETED'},
                                                '2': {'state': 'COMPLETED'},
                                                '3': {'state': 'COMPLETED'}}), ]

MISSION_TREE_2 = [
    test_context.route_generator(),
    test_context.action_generator(params={"should_fail": 1, "time": 3}),
    test_context.route_generator()
]
SCENARIO2_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=1),
    mission_object.MissionStatusV1(state="FAILED", current_node=1,
                                   node_status={'root': {'state': 'FAILED'},
                                                '0': {'state': 'COMPLETED'},
                                                '1': {'state': 'FAILED',
                                                      'error_msg': 'Action failure'},
                                                '2': {'state': 'PENDING'}}), ]

MISSION_TREE_3 = [
    test_context.route_generator(),
    {"name": "selector_1", "selector": {}, "parent": "root"},
    test_context.action_generator(params={"should_fail": 1, "time": 3}, parent="selector_1"),
    test_context.route_generator(parent="selector_1")
]
SCENARIO3_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=2),
    mission_object.MissionStatusV1(state="RUNNING", current_node=3),
    mission_object.MissionStatusV1(state="COMPLETED", current_node=3,
                                   node_status={'root': {'state': 'COMPLETED'},
                                                '0': {'state': 'COMPLETED'},
                                                'selector_1': {'state': 'COMPLETED'},
                                                '2': {'state': 'FAILED', 'error_msg': 'Action failure'},
                                                '3': {'state': 'COMPLETED'}}), ]

MISSION_TREE_4 = [
    test_context.route_generator(),
    {"name": "sequence_1", "sequence": {}, "parent": "root"},
    test_context.action_generator(params={"should_fail": 1, "time": 3}, parent="sequence_1"),
    test_context.route_generator(parent="sequence_1")
]
SCENARIO4_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=2),
    mission_object.MissionStatusV1(state="FAILED", current_node=2,
                                   node_status={'root': {'state': 'FAILED'},
                                                '0': {'state': 'COMPLETED'},
                                                'sequence_1': {'state': 'FAILED'},
                                                '2': {'state': 'FAILED', 'error_msg': 'Action failure'},
                                                '3': {'state': 'PENDING'}}), ]

MISSION_TREE_5 = [
    test_context.route_generator(),
    {"name": "selector_1", "selector": {}, "parent": "root"},
    test_context.action_generator(params={"should_fail": 1, "time": 3}, parent="selector_1"),
    {"name": "sequence_1", "sequence": {}, "parent": "selector_1"},
    test_context.route_generator(parent="sequence_1"),
    test_context.route_generator(parent="sequence_1"),
    test_context.route_generator()
]
SCENARIO5_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=2),
    mission_object.MissionStatusV1(state="RUNNING", current_node=4),
    mission_object.MissionStatusV1(state="RUNNING", current_node=5),
    mission_object.MissionStatusV1(state="RUNNING", current_node=6),
    mission_object.MissionStatusV1(state="COMPLETED", current_node=6,
                                   node_status={'root': {'state': 'COMPLETED'},
                                                '0': {'state': 'COMPLETED'},
                                                'selector_1': {'state': 'COMPLETED'},
                                                '2': {'state': 'FAILED', 'error_msg': 'Action failure'},
                                                'sequence_1': {'state': 'COMPLETED'},
                                                '4': {'state': 'COMPLETED'},
                                                '5': {'state': 'COMPLETED'},
                                                '6': {'state': 'COMPLETED'}}), ]

MISSION_TREE_6 = [
    test_context.route_generator(),
    test_context.action_generator(params={"should_fail": 0, "time": 1}, parent="root", name="pickup"),
    {"name": "selector_1", "selector": {}, "parent": "root"},
    test_context.action_generator(
        params={"should_fail": 1, "time": 1}, parent="selector_1", name="fake_failure_route"),
    {"name": "sequence_1", "sequence": {}, "parent": "selector_1"},
    test_context.route_generator(parent="sequence_1"),
    test_context.action_generator(params={"should_fail": 0, "time": 1}, parent="sequence_1", name="dropoff"),
    {"name": "constant_node", "constant": {
        "success": "false"}, "parent": "sequence_1"},
    test_context.action_generator(params={"should_fail": 0, "time": 1}, parent="root", name="dropoff_at_goal"),
]
SCENARIO6_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=1),
    mission_object.MissionStatusV1(state="RUNNING", current_node=3),
    mission_object.MissionStatusV1(state="RUNNING", current_node=5),
    mission_object.MissionStatusV1(state="RUNNING", current_node=6),
    mission_object.MissionStatusV1(state="FAILED", current_node=7,
                                   node_status={'root': {'state': 'FAILED'},
                                                '0': {'state': 'COMPLETED'},
                                                'pickup': {'state': 'COMPLETED'},
                                                'selector_1': {'state': 'FAILED'},
                                                'fake_failure_route': {'state': 'FAILED', 'error_msg': 'Action failure'},
                                                'sequence_1': {'state': 'FAILED'},
                                                '5': {'state': 'COMPLETED'},
                                                'dropoff': {'state': 'COMPLETED'},
                                                'constant_node': {'state': 'FAILED'},
                                                'dropoff_at_goal': {'state': 'PENDING'}}), ]

MISSION_TREE_7 = [
    test_context.route_generator(),
    test_context.notify_generator(url="",
                                  json_data={
                                      "labels": [],
                                      "battery": {
                                          "critical_level": 0.1
                                      },
                                      "heartbeat_timeout": 30,
                                      "name": "bob"
                                  })]


SCENARIO7_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=1),
    mission_object.MissionStatusV1(state="COMPLETED", current_node=1,
                                   node_status={'root': {'state': 'COMPLETED'},
                                                '0': {'state': 'COMPLETED'},
                                                '1': {'state': 'COMPLETED'}})]

MISSION_TREE_8 = [
    test_context.notify_generator(url="",
                                  json_data={
                                      "labels": [],
                                      "battery": {
                                          "critical_level": 0.1
                                      },
                                      "heartbeat_timeout": 30,
                                      "name": "bob"
                                  })]

SCENARIO8_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="COMPLETED", current_node=0,
                                   node_status={'root': {'state': 'COMPLETED'},
                                                '0': {'state': 'COMPLETED'}})]

# Fail because of duplicate name
MISSION_TREE_9 = [
    test_context.route_generator(),
    test_context.notify_generator(url="",
                                  json_data={
                                      "labels": [],
                                      "battery": {
                                          "critical_level": 0.1
                                      },
                                      "heartbeat_timeout": 30,
                                      "name": "test01"
                                  })]


SCENARIO9_EXPECTED_STATUSES = [
    mission_object.MissionStatusV1(state="PENDING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=0),
    mission_object.MissionStatusV1(state="RUNNING", current_node=1),
    mission_object.MissionStatusV1(state="FAILED", current_node=1,
                                   node_status={'root': {'state': 'FAILED'},
                                                '0': {'state': 'COMPLETED'},
                                                '1': {'state': 'FAILED'}})]


class TestMissionTree(unittest.TestCase):
    """ Test mission tree """

    def test_single_layer_mission_tree(self):
        """ Test single layer tree with routes and actions """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_1))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO1_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break

            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            waypoint = MISSION_TREE_1[-1]["route"]["waypoints"][-1]
            self.assertAlmostEqual(robot_status.pose.x,
                                   waypoint["x"], places=2)
            self.assertAlmostEqual(robot_status.pose.y,
                                   waypoint["y"], places=2)

    def test_single_layer_tree_with_action_failure(self):
        """ Test single layer tree with routes and failure action """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_2))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO2_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.FAILED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break

    def test_selection_node_with_failure_action(self):
        """ Test two-layer tree with selector node and failure action """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_3))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO3_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break

    def test_sequence_node_with_failure_action(self):
        """ Test two-layer tree with sequence node and failure action """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_4))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO4_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break

    def test_three_layer_behavior_tree(self):
        """ Test three-layer tree with selector and sequence control nodes """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_5))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO5_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break
            # Make sure the robot is at the last position in the list of waypoints
            robot_status = ctx.db_client.get(
                api_objects.RobotObjectV1, "test01").status
            waypoint = MISSION_TREE_5[-1]["route"]["waypoints"][-1]
            self.assertAlmostEqual(robot_status.pose.x,
                                   waypoint["x"], places=2)
            self.assertAlmostEqual(robot_status.pose.y,
                                   waypoint["y"], places=2)

    def test_naming(self):
        """ Test if certain name will trigger node translation failure """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        mission_tree = [
            test_context.route_generator(name="route-node"),
            test_context.action_generator(params={"should_fail": 0, "time": 1}, name="action-node")
        ]
        # Expected progression of mission state for the mission `MISSION_TREE_1`
        mission_status = [
            mission_object.MissionStatusV1(state="PENDING", current_node=0),
            mission_object.MissionStatusV1(state="RUNNING", current_node=0),
            mission_object.MissionStatusV1(state="RUNNING", current_node=1),
            mission_object.MissionStatusV1(state="COMPLETED", current_node=1), ]
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            mission = test_context.mission_object_generator(
                "test01", mission_tree)
            mission.name = "my-new-mission"
            ctx.db_client.create(mission)
            # Make sure the mission is updated and completed
            for expected_state, update in zip(mission_status,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    break

    def test_duplicate_node_name(self):
        """ Test if mission fails when have duplicate node names """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        mission_tree = [
            test_context.route_generator(name="route-node", parent="root"),
            test_context.route_generator(name="route-node", parent="root"),
        ]
        with test_context.TestContext([robot]) as ctx:
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            with self.assertRaises(common.ICSUsageError) as cm:
                ctx.db_client.create(
                    test_context.mission_object_generator("test01", mission_tree))
            self.assertTrue("route-node" in str(cm.exception))
            self.assertTrue("repeated" in str(cm.exception))

    def test_nonexist_parent(self):
        """ Test if mission fails when parent doesn't exist """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        mission_tree = [test_context.route_generator(
            name="route-node", parent="root-1")]
        with test_context.TestContext([robot]) as ctx:
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            with self.assertRaises(common.ICSUsageError) as cm:
                ctx.db_client.create(
                    test_context.mission_object_generator("test01", mission_tree))
            self.assertTrue("root-1" in str(cm.exception))
            self.assertTrue("route-node" in str(cm.exception))

    def test_restart_behavior_tree_halfway(self):
        """ Test if behavior works well if we pick up a mission halfway """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        restart_once = False
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_5))

            # Make sure the mission is updated and completed
            completed = False
            watcher = ctx.db_client.watch(api_objects.MissionObjectV1)
            for update in watcher:
                if not restart_once and update.status.node_status['selector_1'].state == "RUNNING":
                    ctx.restart_mission_server()
                    print("Restart mission server", flush=True)
                    restart_once = True
                    continue
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    completed = True
                    break
            self.assertTrue(completed)

    def test_constant_node(self):
        """ Test three-layer tree with the constant node """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_6))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO6_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break

    def test_route_with_notify_node(self):
        """ Test simple tree with notify node """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Use Mission Dispatch POST /robot to test
            MISSION_TREE_7[1]['notify']['url'] = f"http://{ctx.database_address}:5003/robot"
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_7))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO7_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break

    def test_single_notify_node(self):
        """ Test tree with single notify node """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Use Mission Dispatch POST /robot to test
            MISSION_TREE_8[0]['notify']['url'] = f"http://{ctx.database_address}:5003/robot"
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_8))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO8_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break

    def test_failed_notify_node(self):
        """ Test simple tree with failed notify node """
        robot = simulator.RobotInit("test01", 0, 0, 0)
        with test_context.TestContext([robot]) as ctx:
            # Use Mission Dispatch POST /robot to test
            MISSION_TREE_9[1]['notify']['url'] = f"http://{ctx.database_address}:5003/robot"
            # Create the robot and then the mission
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            ctx.db_client.create(
                test_context.mission_object_generator("test01", MISSION_TREE_9))
            # Make sure the mission is updated and completed
            for expected_state, update in zip(SCENARIO9_EXPECTED_STATUSES,
                                              ctx.db_client.watch(api_objects.MissionObjectV1)):
                self.assertEqual(update.status.state, expected_state.state)
                self.assertEqual(update.status.current_node,
                                 expected_state.current_node)
                if update.status.state == mission_object.MissionStateV1.COMPLETED:
                    self.assertEqual(update.status.node_status,
                                     expected_state.node_status)
                    break


if __name__ == "__main__":
    unittest.main()
