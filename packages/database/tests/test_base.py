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
import multiprocessing
import os
import signal
from typing import Any, List, Tuple

import unittest

import packages.objects as api_objects
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

    def run_docker(cls, image: str, args: List[str], docker_args: List[str] = None,
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
        robot0_from_db = self.client.get(api_objects.RobotObjectV1, robot0.name)
        robot1_from_db = self.client.get(api_objects.RobotObjectV1, robot1.name)
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
        robot0_from_db = self.client.get(api_objects.RobotObjectV1, robot0.name)
        robot1_from_db = self.client.get(api_objects.RobotObjectV1, robot1.name)
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
        robot0_from_db = self.client.get(api_objects.RobotObjectV1, robot0.name)
        robot1_from_db = self.client.get(api_objects.RobotObjectV1, robot1.name)
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
        self.assertEqual(fetched_robot.lifecycle, api_objects.ObjectLifecycleV1.PENDING_DELETE)

        # User should not be able to update status
        with self.assertRaises(ValueError):
            self.client.update_status(robot0)

        # Controller should not be able to update spec
        with self.assertRaises(ValueError):
            self.controller_client.update_spec(robot0)

        self.controller_client.delete(api_objects.RobotObjectV1, robot0.name)

    def test_watch(self):
        """ Test method /watch"""
        # Method /watch should return all items of a given type in the DB
        # Method /watch should notify when an object is created
        watcher_client = self.client.watch(api_objects.RobotObjectV1)
        watcher_controller_client = self.controller_client.watch(api_objects.RobotObjectV1)
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
        self.assertEqual(update_client.lifecycle, api_objects.ObjectLifecycleV1.PENDING_DELETE)
        self.assertEqual(update_controller_client.lifecycle,
                         api_objects.ObjectLifecycleV1.PENDING_DELETE)
