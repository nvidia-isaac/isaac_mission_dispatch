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
import multiprocessing
import os
import signal
import datetime
from typing import Any, List, Tuple, Dict, Union

import unittest

import cloud_common.objects as api_objects
from cloud_common.objects.robot import RobotStateV1
from cloud_common.objects.robot import RobotTypeV1
from cloud_common.objects.mission import MissionStateV1, MissionNodeV1
from cloud_common.objects.detection_results import DetectedObject, DetectedObjectBoundingBox2D
from packages.utils import test_utils

# A label to add to a robot to demonstrate modifing the spec
DEFAULT_LABEL = "test1"


class TestDatabase(unittest.TestCase):
    """
    Base test class for common tests for memory and postgres db
    """
    controller_client: Any = None
    client: Any = None
    has_process_crashed = False

    def catch_signal(cls, s, frame):
        TestDatabase.has_process_crashed = True
        raise OSError("Child process crashed!")

    def run_docker(cls, image: str, args: List[str], docker_args: Union[List[str], None] = None,
                   delay: int = 0) -> Tuple[multiprocessing.Process, str]:
        pid = os.getpid()
        queue: multiprocessing.queues.Queue[str] = multiprocessing.Queue()

        def wrapper_process():
            docker_process, address = \
                test_utils.run_docker_target(image, args=args,
                                             docker_args=docker_args, delay=delay)
            queue.put(address)
            docker_process.wait()
            os.kill(pid, signal.SIGUSR1)

        process = multiprocessing.Process(target=wrapper_process, daemon=True)
        process.start()
        return process, queue.get()

    def close(cls, processes):
        for process in processes:
            if process is not None:
                process.terminate()
                process.join()

    def test_insert_fetch(self):
        robots = [api_objects.RobotObjectV1(status={}, name=("carter0" + str(i)))
                  for i in range(0, 10)]
        inserted_robots = []

        # First, make sure the robot is empty
        all_robots = self.client.list(api_objects.RobotObjectV1)
        self.assertCountEqual(all_robots, [])

        # Insert the robots one by one and make sure they are added
        while robots:
            new_robot = robots.pop()
            inserted_robots.append(new_robot)
            self.client.create(new_robot)
            all_robots = self.client.list(api_objects.RobotObjectV1)
            self.assertCountEqual(all_robots, inserted_robots)

        # Make sure we can get two robots by id
        robot0 = inserted_robots[0]
        robot1 = inserted_robots[1]
        robot0_from_db = self.client.get(
            api_objects.RobotObjectV1, robot0.name)
        robot1_from_db = self.client.get(
            api_objects.RobotObjectV1, robot1.name)
        self.assertEqual(robot0, robot0_from_db)
        self.assertNotEqual(robot0, robot1_from_db)
        self.assertEqual(robot1, robot1_from_db)
        self.assertNotEqual(robot1, robot0_from_db)

        for i in range(0, 10):
            name = f"carter0{str(i)}"
            self.controller_client.delete(api_objects.RobotObjectV1, name)

    def test_update_spec(self):
        # Create two robot objects
        robot0 = api_objects.RobotObjectV1(status={}, name="carter00")
        robot1 = api_objects.RobotObjectV1(status={}, name="carter01")
        self.client.create(robot0)
        self.client.create(robot1)

        # Update the spec of one of them and the state of the other
        robot0.labels.append(DEFAULT_LABEL)
        robot1.status.pose.x = 1
        self.client.update_spec(robot0)
        self.client.update_spec(robot1)

        # Make sure the objects returned from the DB match
        robot0_from_db = self.client.get(
            api_objects.RobotObjectV1, robot0.name)
        robot1_from_db = self.client.get(
            api_objects.RobotObjectV1, robot1.name)
        self.assertEqual(robot0, robot0_from_db)
        self.assertEqual(robot1.name, robot1_from_db.name)
        self.assertEqual(robot1.labels, robot1_from_db.labels)
        self.assertNotEqual(robot1.status, robot1_from_db.status)

        self.controller_client.delete(api_objects.RobotObjectV1, robot0.name)
        self.controller_client.delete(api_objects.RobotObjectV1, robot1.name)

    def test_update_status(self):
        # Create two robot objects
        robot0 = api_objects.RobotObjectV1(status={}, name="carter00")
        robot1 = api_objects.RobotObjectV1(status={}, name="carter01")
        self.client.create(robot0)
        self.client.create(robot1)

        # Update the spec of one of them and the state of the other
        robot0.labels.append(DEFAULT_LABEL)
        robot1.status.pose.x = 1
        self.controller_client.update_status(robot0)
        self.controller_client.update_status(robot1)

        # Make sure the objects returned from the DB match
        robot0_from_db = self.client.get(
            api_objects.RobotObjectV1, robot0.name)
        robot1_from_db = self.client.get(
            api_objects.RobotObjectV1, robot1.name)
        self.assertEqual(robot1, robot1_from_db)
        self.assertEqual(robot0.name, robot0_from_db.name)
        self.assertEqual(robot0.status, robot0_from_db.status)
        self.assertNotEqual(robot0.labels, robot0_from_db.labels)

        self.controller_client.delete(api_objects.RobotObjectV1, robot0.name)
        self.controller_client.delete(api_objects.RobotObjectV1, robot1.name)

    def test_permissions(self):
        robot0 = api_objects.RobotObjectV1(status={}, name="carter00")
        self.client.create(robot0)

        # User should not be able to hard delete
        self.client.delete(api_objects.RobotObjectV1, robot0.name)
        fetched_robot = self.client.get(api_objects.RobotObjectV1, robot0.name)
        self.assertEqual(fetched_robot.lifecycle,
                         api_objects.ObjectLifecycleV1.PENDING_DELETE)

        # User should not be able to update status
        with self.assertRaises(api_objects.common.ICSUsageError):
            self.client.update_status(robot0)

        # Controller should not be able to update spec
        with self.assertRaises(api_objects.common.ICSUsageError):
            self.controller_client.update_spec(robot0)

        self.controller_client.delete(api_objects.RobotObjectV1, robot0.name)

    def test_watch(self):
        """ Test method /watch"""
        # Method /watch should return all items of a given type in the DB
        # Method /watch should notify when an object is created
        watcher_client = self.client.watch(api_objects.RobotObjectV1)
        watcher_controller_client = self.controller_client.watch(
            api_objects.RobotObjectV1)
        robot0 = api_objects.RobotObjectV1(status={}, name="carter00")
        self.client.create(robot0)
        update = next(watcher_controller_client)
        self.assertEqual(robot0, update)

        # Method /watch should notify when status is updated
        robot0.status.pose.x = 1
        self.controller_client.update_status(robot0)
        update = next(watcher_client)
        self.assertEqual(robot0.status.pose.x, update.status.pose.x)

        # Method /watch should notify when spec is updated
        robot0.labels.append(DEFAULT_LABEL)
        self.client.update_spec(robot0)
        update = next(watcher_controller_client)
        self.assertEqual(robot0.labels[-1], update.labels[-1])

        # Method /watch should notify when an object is deleted
        self.client.delete(api_objects.RobotObjectV1, robot0.name)
        update_client = next(watcher_client)
        update_controller_client = next(watcher_controller_client)
        self.assertEqual(update_client.lifecycle,
                         api_objects.ObjectLifecycleV1.PENDING_DELETE)
        self.assertEqual(update_controller_client.lifecycle,
                         api_objects.ObjectLifecycleV1.PENDING_DELETE)

    def setup_carter_robots(self):
        # Robots
        # -----------------------------------------
        # name      battery     state       online
        # carter00  0           IDLE        true
        # carter01  10          ON_TASK     true
        # carter02  20          IDLE        false
        # carter03  30          ON_TASK     false
        # carter04  40          IDLE        true
        # carter05  50          ON_TASK     true
        # carter06  60          IDLE        false
        # carter07  70          ON_TASK     false
        # carter08  80          IDLE        true
        # carter09  90          ON_TASK     true

        robots = [api_objects.RobotObjectV1(status={}, name="carter0" + str(i))
                  for i in range(0, 10)]

        for robot in robots:
            self.client.create(robot)

        for i, robot in enumerate(robots):
            # Battery for each robot to i * 10
            robot.status.battery_level = i * 10

            # Even numbered robots are IDLE, odd are ON_TASK
            robot.status.state = RobotStateV1.IDLE if i % 2 == 0 else RobotStateV1.ON_TASK
            robot.status.factsheet.agv_class = RobotTypeV1.AMR.value
            # For every two robots, alternate online to true and false
            # i.e. carter0, carter1 are true, carter2, carter3 are false, etc.
            robot.status.online = i % 4 <= 1

        for robot in robots:
            self.controller_client.update_status(robot)

        return robots

    def setup_carter_and_arm_robots(self):
        robots = [api_objects.RobotObjectV1(status={}, name="arm01"),
                  api_objects.RobotObjectV1(status={}, name="carter01")]

        for robot in robots:
            self.client.create(robot)

        # Add a single arm
        robots[0].status.factsheet.agv_class = RobotTypeV1.ARM.value

        # Add a single carter
        robots[1].status.factsheet.agv_class = RobotTypeV1.AMR.value

        for robot in robots:
            self.controller_client.update_status(robot)

        return robots

    def setup_arm_and_detection_results(self):
        robots = [api_objects.RobotObjectV1(status={}, name="arm01")]
        detection_results = [
            api_objects.DetectionResultsObjectV1(name="arm01")]

        for robot in robots:
            self.client.create(robot)

        for detection_result in detection_results:
            self.controller_client.create(detection_result)

        # Add a single arm
        robots[0].status.factsheet.agv_class = RobotTypeV1.ARM.value

        # Set up dummy response from object detection
        detection_results[0].status.detected_objects = [
            DetectedObject(bbox2d=DetectedObjectBoundingBox2D())]

        # Changing an entry in the uploaded object
        detection_results[0].status.detected_objects[0].object_id = 4

        for robot in robots:
            self.controller_client.update_status(robot)

        for detection_result in detection_results:
            self.controller_client.update_status(detection_result)

        return robots, detection_results

    def cleanup_robots(self, robots):
        for robot in robots:
            self.controller_client.delete(
                api_objects.RobotObjectV1, robot.name)

    def cleanup_detection_results(self, detection_results):
        for detection_result in detection_results:
            self.controller_client.delete(
                api_objects.DetectionResultsObjectV1, detection_result.name)

    def test_list_robot_with_battery_state_online(self):
        # Set up robots
        robots = self.setup_carter_robots()

        # Should return all if no parameters given
        all_robots = self.client.list(api_objects.RobotObjectV1)
        assert len(all_robots) == len(robots)

        # Should work with only min_battery query
        battery_ge_50 = self.client.list(
            api_objects.RobotObjectV1, {"min_battery": 50})
        assert len(battery_ge_50) == 5

        battery_ge_90 = self.client.list(
            api_objects.RobotObjectV1, {"min_battery": 90})
        assert len(battery_ge_90) == 1
        assert robots[9] == battery_ge_90[0]

        battery_ge_91 = self.client.list(
            api_objects.RobotObjectV1, {"min_battery": 91})
        assert len(battery_ge_91) == 0

        # Should work with only state query
        idle_robots = self.client.list(
            api_objects.RobotObjectV1, {"state": "IDLE"})
        assert len(idle_robots) == 5

        # Should work with only online query
        online_robots = self.client.list(
            api_objects.RobotObjectV1, {"online": True})
        assert len(online_robots) == 6

        # --- Combination tests ---

        # Get robots that have min_battery >= 55 and IDLE
        params = {
            "min_battery": 55,
            "state": "IDLE"
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 2
        assert robots[6] in output
        assert robots[8] in output

        # Get robots that are IDLE and online
        params = {
            "state": "IDLE",
            "online": True
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 3
        assert robots[0] in output
        assert robots[4] in output
        assert robots[8] in output

        # Get robots that have min_battery >= 28 and online
        params = {
            "min_battery": 28,
            "online": True
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 4
        assert robots[4] in output
        assert robots[5] in output
        assert robots[8] in output
        assert robots[9] in output

        # Get robots that have min_battery >= 55 and IDLE and online
        params = {
            "min_battery": 55,
            "state": "IDLE",
            "online": True
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 1
        assert robots[8] == output[0]

        # Test names
        params = {
            "names": ["carter01", "carter03", "carter09"]
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 3
        assert robots[1] in output
        assert robots[3] in output
        assert robots[9] in output

        # Clean up
        self.cleanup_robots(robots)

    def test_list_robot_names(self):
        robots = self.setup_carter_robots()

        # Test names
        params: Dict[str, Any] = {
            "names": ["carter01", "carter03", "carter04", "carter09"]
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 4
        assert robots[1] in output
        assert robots[3] in output
        assert robots[4] in output
        assert robots[9] in output

        # Test names with battery and state
        params = {
            "names": ["carter01", "carter03", "carter04", "carter09"],
            "min_battery": 30,
            "state": "IDLE"
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 1
        assert robots[4] == output[0]

        self.cleanup_robots(robots)

    def test_mission_queries(self):
        tree = [MissionNodeV1(selector={})]
        missions = [
            api_objects.MissionObjectV1(
                name="mission0", robot="0", mission_tree=tree, status={}),
            api_objects.MissionObjectV1(
                name="mission1", robot="1", mission_tree=tree, status={}),
            api_objects.MissionObjectV1(
                name="mission2", robot="2", mission_tree=tree, status={})
        ]
        for mission in missions:
            self.client.create(mission)

        # Mission0 started at 2001/1/1, state = PENDING
        missions[0].status.start_timestamp = datetime.datetime(2001, 1, 1)
        missions[0].status.state = MissionStateV1.PENDING

        # Mission1 started at 2002/2/2, state = COMPLETED
        missions[1].status.start_timestamp = datetime.datetime(2002, 2, 2)
        missions[1].status.state = MissionStateV1.COMPLETED

        # Mission2 started at 2003/3/3, state = FAILED
        missions[2].status.start_timestamp = datetime.datetime(2003, 3, 3)
        missions[2].status.state = MissionStateV1.FAILED

        for mission in missions:
            self.controller_client.update_status(mission)

        params: Dict[str, Any] = {
            "started_after": datetime.datetime(2001, 1, 1)
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 3

        params = {
            "started_after": datetime.datetime(2001, 1, 2)
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 2

        params = {
            "started_after": datetime.datetime(2002, 12, 30)
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 1
        assert missions[2] == returned_missions[0]

        params = {
            "started_after": datetime.datetime(2002, 1, 1),
            "started_before": datetime.datetime(2003, 1, 1)
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 1
        assert missions[1] == returned_missions[0]

        params = {
            "started_after": datetime.datetime(2000, 1, 1),
            "started_before": datetime.datetime(2002, 1, 1),
            "state": "PENDING"
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 1
        assert missions[0] == returned_missions[0]

        params = {
            "most_recent": 1
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 1
        assert missions[2] == returned_missions[0], returned_missions[0]

        params = {
            "most_recent": 2
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 2
        assert missions[2] == returned_missions[0]
        assert missions[1] == returned_missions[1]

        params = {
            "started_before": datetime.datetime(2003, 1, 1),
            "most_recent": 1
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 1
        assert missions[1] == returned_missions[0]

        params = {
            "robot": "0"
        }
        returned_missions = self.client.list(
            api_objects.MissionObjectV1, params)
        assert len(returned_missions) == 1
        assert missions[0] == returned_missions[0]

    def test_list_arm_names(self):
        robots = self.setup_carter_and_arm_robots()

        # Test AMR query
        params = {
            "robot_type": [RobotTypeV1.AMR.value]
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        print("Number of AMRs: " + str(len(output)))
        assert len(output) == 1
        assert robots[1] in output

        # Test arm query
        params = {
            "robot_type": [RobotTypeV1.ARM.value]
        }
        output = self.client.list(api_objects.RobotObjectV1, params)
        assert len(output) == 1
        assert robots[0] in output

        self.cleanup_robots(robots)

    def test_detection_results_push(self):
        robots, detection_results = self.setup_arm_and_detection_results()
        output = self.client.list(api_objects.DetectionResultsObjectV1)

        assert len(output) == 1
        assert detection_results[0] in output
        assert output[0].status.detected_objects[0].object_id == 4

        self.cleanup_detection_results(detection_results)
        self.cleanup_robots(robots)
