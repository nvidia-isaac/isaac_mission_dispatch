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
import os
import multiprocessing
import random
import time
import signal
from typing import Dict, List, NamedTuple, Tuple, Optional

from cloud_common import objects as api_objects
from cloud_common.objects import robot as robot_object
from packages.controllers.mission.tests import client as simulator
from packages.database import client as db_client
from packages.utils import test_utils
import requests
import logging

# The TCP port for the api server to listen on
DATABASE_PORT = 5003
# The TCP port for the api server to listen for controller traffic
DATABASE_CONTROLLER_PORT = 5004
# The TCP port for the MQTT broker to listen on
MQTT_PORT_TCP = 1885
# The WEBSOCKET port for the MQTT broker to listen on
MQTT_PORT_WEBSOCKET = 9001
# The transport mechanism("websockets", "tcp") for MQTT
MQTT_TRANSPORT = "websockets"
# The path for the websocket if 'mqtt_transport' is 'websockets'"
MQTT_WS_PATH = "/mqtt"
# The port for the MQTT broker to listen on
MQTT_PORT = MQTT_PORT_TCP if MQTT_TRANSPORT == "tcp" else MQTT_PORT_WEBSOCKET
# How far the simulator should move the robots each second
SIM_SPEED = 10
# Starting PostgreSQL Db on this port
POSTGRES_DATABASE_PORT = 5432
# The MQTT topic prefix
MQTT_PREFIX = "uagv/v2/RobotCompany"


class Delay(NamedTuple):
    mqtt_broker: int = 0
    mission_dispatch: int = 0
    mission_database: int = 0
    mission_simulator: int = 0


class TestContext:
    crashed_process = False

    def __init__(self, robots, name="test context", delay: Delay = Delay(),
                 tick_period: float = 0.25, enforce_start_order: bool = True, fail_as_warning=False):
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger("Isaac Mission Dispatch Test Context")
        if TestContext.crashed_process:
            raise ValueError("Can't run test due to previous failure")

        # Set random seed to get pseudo-random numbers for consistent testing result
        random.seed(0)

        self._robots = robots
        self._name = name

        fail_as_warning = fail_as_warning or any(
            robot.fail_as_warning for robot in robots)

        self.logger.info(f"Opening context: {self._name}")

        # Register signal handler
        signal.signal(signal.SIGUSR1, self.catch_signal)

        # Start postgreSQL db
        self._postgres_database, postgres_address = \
            self.run_docker(image="//packages/utils/test_utils:postgres-database-img-bundle",
                            docker_args=["-e", "POSTGRES_PASSWORD=postgres",
                                         "-e", "POSTGRES_DB=mission",
                                         "-e", "POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256"],
                            args=['postgres'])
        test_utils.wait_for_port(
            host=postgres_address, port=POSTGRES_DATABASE_PORT, timeout=120)

        # Start the database
        self._database_process, self.database_address = \
            self.run_docker(image="//packages/database:postgres-img-bundle",
                            args=["--port", str(DATABASE_PORT),
                                  "--controller_port", str(
                                      DATABASE_CONTROLLER_PORT),
                                  "--db_host", postgres_address,
                                  "--db_port", str(POSTGRES_DATABASE_PORT),
                                  "--address", "0.0.0.0"])

        # Start the Mosquitto broker
        self._mqtt_process, self.mqtt_address = self.run_docker(
            "//packages/utils/test_utils:mosquitto-img-bundle",
            args=[str(MQTT_PORT_TCP), str(MQTT_PORT_WEBSOCKET)],
            delay=delay.mqtt_broker)

        # Wait for both broker and db to start
        if enforce_start_order:
            self.wait_for_mqtt()
            self.wait_for_database()

        # Start mission server
        self._server_process, _ = self.run_docker(
            "//packages/controllers/mission:mission-img-bundle",
            args=["--mqtt_port", str(MQTT_PORT),
                  "--mqtt_host", self.mqtt_address,
                  "--mqtt_transport", str(MQTT_TRANSPORT),
                  "--mqtt_ws_path", str(MQTT_WS_PATH),
                  "--mqtt_prefix", str(MQTT_PREFIX),
                  "--database_url", f"http://{self.database_address}:{DATABASE_CONTROLLER_PORT}"],
            delay=delay.mission_dispatch)

        # Start simulator
        sim_args = ["--robots", " ".join(str(robot) for robot in self._robots),
                    "--speed", str(SIM_SPEED),
                    "--mqtt_port", str(MQTT_PORT),
                    "--mqtt_host", self.mqtt_address,
                    "--mqtt_transport", str(MQTT_TRANSPORT),
                    "--mqtt_ws_path", str(MQTT_WS_PATH),
                    "--mqtt_prefix", str(MQTT_PREFIX),
                    "--tick_period", str(tick_period)]
        if fail_as_warning:
            sim_args.append("--fail_as_warning")

        self._sim_process, _ = self.run_docker("//packages/controllers/mission/tests:client-img-bundle",
                                               args=sim_args,
                                               delay=delay.mission_simulator)

        # Create db client
        self.md_url = f"http://{self.database_address}:{DATABASE_PORT}"
        self.db_client = db_client.DatabaseClient(self.md_url)
        self.md_ctrl_url = f"http://{self.database_address}:{DATABASE_CONTROLLER_PORT}"
        self.db_controller_client = db_client.DatabaseClient(self.md_ctrl_url)

    def wait_for_database(self):
        test_utils.wait_for_port(
            host=self.database_address, port=DATABASE_PORT, timeout=120)

    def wait_for_mqtt(self):
        test_utils.wait_for_port(
            host=self.mqtt_address, port=MQTT_PORT, timeout=120)

    def restart_mission_server(self):
        self.close([self._server_process])
        time.sleep(1)
        self._server_process, _ = self.run_docker(
            "//packages/controllers/mission:mission-img-bundle",
            args=["--mqtt_port", str(MQTT_PORT),
                  "--mqtt_host", self.mqtt_address,
                  "--mqtt_transport", str(MQTT_TRANSPORT),
                  "--mqtt_ws_path", str(MQTT_WS_PATH),
                  "--mqtt_prefix", str(MQTT_PREFIX),
                  "--database_url", f"http://{self.database_address}:{DATABASE_CONTROLLER_PORT}"])

    def restart_mqtt_server(self):
        # Restart the Mosquitto broker
        self.close([self._mqtt_process])
        time.sleep(1)
        self._mqtt_process, self.mqtt_address = self.run_docker(
            "//packages/utils/test_utils:mosquitto-img-bundle",
            args=[str(MQTT_PORT_TCP), str(MQTT_PORT_WEBSOCKET)])
        self.wait_for_mqtt()

    def catch_signal(self, signal, frame):
        TestContext.crashed_process = True
        raise OSError("Child process crashed!")

    def run_docker(self, image: str, args: List[str], docker_args: List[str] = None,
                   delay: float = 0.0) -> Tuple[multiprocessing.Process, str]:
        pid = os.getpid()
        queue = multiprocessing.Queue()

        def wrapper_process():
            docker_process, address = \
                test_utils.run_docker_target(
                    image, args=args, docker_args=docker_args, delay=delay)
            queue.put(address)
            docker_process.wait()
            os.kill(pid, signal.SIGUSR1)

        process = multiprocessing.Process(target=wrapper_process, daemon=True)
        process.start()
        return process, queue.get()

    def close(self, processes):
        for process in processes:
            if process is not None:
                process.terminate()
                process.join()
                process.close()

    def call_teleop_service(self, robot_name: str, teleop: robot_object.RobotTeleopActionV1):
        endpoint = self.md_url + f"/robot/{robot_name}/teleop"
        response = requests.post(url=endpoint, params={"params": teleop.value})
        if response.status_code == 200:
            self.logger.info(f"Teleop {teleop.value} request sent")
        else:
            self.logger.info(f"Teleop {teleop.value} failed")

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close([self._server_process, self._database_process,
                    self._postgres_database, self._mqtt_process, self._sim_process])
        self.logger.info(f"Context closed: {self._name}")


def mission_from_waypoints(robot: str, waypoints, name: Optional[str] = None, timeout: int = 1000):
    """Converts a (x, y) coordinate into a mission object"""
    return api_objects.MissionObjectV1(
        name=name,
        robot=robot,
        mission_tree=[
            {"route": {"waypoints": [{"x": x, "y": y, "theta": 0}]}} for x, y in waypoints
        ],
        status={},
        timeout=timeout)


def mission_from_waypoint(robot: str, x: float, y: float, name: Optional[str] = None):
    """Converts a (x, y) coordinate into a mission object"""
    return mission_from_waypoints(robot, [(x, y)], name)


def pose1D_generator(pose_scale=3, min_dist=0.5):
    """Generate random 1D pose within certain range

    Args:
        pose_scale (int, optional): range from 0 to pose_scale. Defaults to 3.
        min_dist (float, optional): minimum value of the point. Defaults to 0.5.

    Returns:
        float: 1D pose
    """
    return round(random.random() * pose_scale + min_dist, 1)


def route_generator(parent: str = "root", name: str = None):
    """ Generate route dict

    Args:
        parent: parent name
        name: node name

    Returns:
        Dict: route mission node
    """
    waypoints_size = random.randint(1, 4)
    waypoints = {"waypoints": [{"x": pose1D_generator(), "y": pose1D_generator(), "theta": 0}
                               for _ in range(waypoints_size)]}
    route_dict = {"route": waypoints, "parent": parent}
    if name is not None:
        route_dict.update({"name": name})
    return route_dict


def move_generator(parent: str = "root", name: str = None, move: dict = {}):
    """ Generate move dict

    Args:
        parent: parent name
        name: node name

    Returns:
        Dict: move mission node
    """
    move_dict = {"move": move, "parent": parent}
    if name is not None:
        move_dict.update({"name": name})
    return move_dict


def action_generator(params: dict, parent: str = "root",
                     name: str = None, action_type: str = "dummy_action") -> Dict:
    """ Generate action mission node

    Args:
        params: action parameters
        parent: parent name
        name: node name
        action_type: type of the action

    Returns:
        Dict: action mission node
    """
    action_dict = {"parent": parent,
                   "action": {"action_type": action_type,
                              "action_parameters": params}}
    if name is not None:
        action_dict.update({"name": name})
    return action_dict


def notify_generator(url: str, json_data: Dict,
                     parent: str = "root", name: str = None) -> Dict:
    """ Generate notify mission node

    Args:
        url (str): URL to make API call
        json_data (Dict): JSON payload to be included in API call.
        parent: parent name
        name: node name

    Returns:
        Dict: notify mission node
    """
    notify_dict = {"parent": parent,
                   "notify": {
                       "url": url,
                       "json_data": json_data
                   }}
    if name is not None:
        notify_dict.update({"name": name})
    return notify_dict


def mission_object_generator(robot: str, mission_tree, timeout=1000):
    """Converts a mission tree into a mission object"""
    return api_objects.MissionObjectV1(
        robot=robot,
        mission_tree=mission_tree,
        status={}, timeout=timeout)
