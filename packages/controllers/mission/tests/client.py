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

# This repository implements data types and logic specified in the VDA5050 protocol, which is
# specified here https://github.com/VDA5050/VDA5050/blob/main/VDA5050_EN.md
import argparse
import copy
import datetime
import json
import logging
import re
import socket
import time
from typing import Dict, List, Optional, Union

import paho.mqtt.client as mqtt_client
import pydantic

import packages.controllers.mission.vda5050_types as types

DISTANCE_THRESHOLD = 0.05

# How long to wait in seconds before trying to reconnect to the mqtt broker
MQTT_RECONNECT_PERIOD = 0.5

LOGGING_NAME = "Isaac Mission Dispatch Client Simulator"


class ActionObject:
    """Action Object"""

    def __init__(self, action_type: Union[types.NVActionType,
                                          types.VDA5050InstantActionType,
                                          types.NVInstantActionType]):
        self._action_type = action_type
        self._status = types.VDA5050ActionStatus.WAITING

    @property
    def triggered(self):
        return self._status != types.VDA5050ActionStatus.WAITING

    @property
    def finished(self):
        return self._status == types.VDA5050ActionStatus.FINISHED

    @property
    def failed(self):
        return self._status == types.VDA5050ActionStatus.FAILED

    @property
    def get_status(self):
        return self._status

    def reset(self):
        self._status = types.VDA5050ActionStatus.WAITING

    def update_status(self):
        pass


class DummyActionServer(ActionObject):
    """Represents an action server that executes action and sends feedbacks"""

    def __init__(self):
        self._should_fail = False
        self._completed_time = float("inf")
        self.logger = logging.getLogger(LOGGING_NAME)
        super().__init__(types.NVActionType.DUMMY_ACTION)

    def start(self, params):
        # Determine the time when the mission will fail/finish
        self.logger.info("Start dummy action")
        if "should_fail" in params and "time" in params:
            self._should_fail = json.loads(params["should_fail"])
            self._completed_time = time.time() + float(params["time"])
            self._status = types.VDA5050ActionStatus.RUNNING
        else:
            self._status = types.VDA5050ActionStatus.FAILED
            self.logger.info("Missing params in action {}")

    def update_status(self):
        # If this has been running for at least execution_time
        if time.time() < self._completed_time:
            self._status = types.VDA5050ActionStatus.RUNNING
        else:
            if self._should_fail:
                self._status = types.VDA5050ActionStatus.FAILED
            else:
                self._status = types.VDA5050ActionStatus.FINISHED
        return self._status


class CancelOrderInstantActionServer(ActionObject):
    """An action server that executes order cancelation"""

    def __init__(self) -> None:
        self.action_id = ""
        super().__init__(types.VDA5050InstantActionType.CANCEL_ORDER)

    def update_status(self, status):
        self._status = status

    def set_action_id(self, action_id: str):
        self.action_id = action_id


class TeleopActionServer(ActionObject):
    """An action server that executes order cancelation"""

    def __init__(self, robot) -> None:
        self.robot = robot
        self.logger = logging.getLogger(LOGGING_NAME)
        super().__init__(types.NVActionType.PAUSE_ORDER)

    def start(self, params=None):
        self.logger.info("Start teleop action")
        self._status = types.VDA5050ActionStatus.RUNNING
        self.robot.pause_order = True

    def update_status(self):
        if self.robot.pause_order:
            self._status = types.VDA5050ActionStatus.RUNNING
        else:
            self._status = types.VDA5050ActionStatus.FINISHED


class MapLoadActionServer(ActionObject):
    """An action server that executes order cancelation"""

    def __init__(self, robot) -> None:
        self.robot = robot
        self.logger = logging.getLogger(LOGGING_NAME)
        super().__init__(types.NVActionType.LOAD_MAP)

    def start(self, params):
        self.logger.info("Start map loading action")
        self._status = types.VDA5050ActionStatus.RUNNING
        # Simulate map loading for 1s
        self._completed_time = time.time() + 1
        self.robot.state.agvPosition.mapId = params["map_id"]

    def update_status(self):
        if time.time() < self._completed_time:
            self._status = types.VDA5050ActionStatus.RUNNING
        else:
            self._status = types.VDA5050ActionStatus.FINISHED
        return self._status


class DockingActionServer(ActionObject):
    """An action server that executes order cancelation"""

    def __init__(self, robot) -> None:
        self.robot = robot
        self.logger = logging.getLogger(LOGGING_NAME)
        super().__init__(types.NVActionType.DOCK_ROBOT)

    def start(self, params=None):
        self.logger.info("Start docking action")
        self._status = types.VDA5050ActionStatus.RUNNING
        # Simulate dorking for 5s
        self._completed_time = time.time() + 5

    def update_status(self):
        if time.time() < self._completed_time:
            self._status = types.VDA5050ActionStatus.RUNNING
        else:
            self._status = types.VDA5050ActionStatus.FINISHED
        return self._status


class RobotInit:
    """Represents the initial state of a robot in the simulation"""

    def __init__(self, name: str, x: float, y: float, theta: float = 0.0, map_id: str = "map",
                 failure_period: int = 0, battery: float = 0.0,
                 manufacturer: str = "", serial_number: str = "",
                 fail_as_warning=False):
        self.name = name
        self.x = x
        self.y = y
        self.theta = theta
        self.map_id = map_id
        self.failure_period = failure_period
        self.battery = battery
        self.manufacturer = manufacturer
        self.serial_number = serial_number
        self.fail_as_warning = fail_as_warning

    def __str__(self) -> str:
        params = [self.name, self.x, self.y, self.theta,
                  self.map_id, self.failure_period, self.battery]
        if self.manufacturer != "":
            params.append(self.manufacturer)
        if self.serial_number != "":
            params.append(self.serial_number)
        return ",".join(str(param) for param in params)


class Robot:
    """Represents and handles the movement of a simulated robot"""

    def __init__(self, init: RobotInit, client: mqtt_client.Client, speed: float,
                 tick_period: float = 0.25, mqtt_prefix: str = "uagv/v2/Company",
                 metrics_dir: Optional[str] = None, fail_as_warning: bool = False):
        self.logger = logging.getLogger(LOGGING_NAME)
        self.name = init.name
        self.order: Optional[types.VDA5050Order] = None
        self.state = types.VDA5050OrderInformation(
            headerId=0,
            timestamp="",
            manufacturer=init.manufacturer,
            serialNumber=init.serial_number,
            orderId="",
            orderUpdateId=0,
            lastNodeId="",
            lastNodeSequenceId=0,
            nodeStates=[],
            edgeStates=[],
            agvPosition={"x": init.x, "y": init.y,
                         "theta": init.theta, "mapId": init.map_id},
            actionStates=[],
            batteryState={"batteryCharge": init.battery,
                          "charging": False})
        self.client = client
        self.failure_period = init.failure_period
        self.fail_as_warning = fail_as_warning or init.fail_as_warning
        self.time_to_next_failure = 0
        self.speed = speed
        self.tick_period = tick_period
        self.pause_order = False
        self._current_node = 0
        self._current_action_id = 0
        self._mqtt_prefix = mqtt_prefix
        self._metric: Dict = {}
        self._metrics: List = []
        self._save_metrics = False
        self._metrics_dir = metrics_dir
        self._cancel_order_action_server = CancelOrderInstantActionServer()
        self._dummy_action_server = DummyActionServer()
        self._map_load_action_server = MapLoadActionServer(robot=self)
        self._teleop_action_server = TeleopActionServer(robot=self)
        self._docking_action_server = DockingActionServer(robot=self)

    @property
    def action_server_triggered(self):
        return self._map_load_action_server.triggered or \
            self._dummy_action_server.triggered or \
            self._teleop_action_server.triggered or \
            self._docking_action_server.triggered

    def publish_state(self):
        self.state.timestamp = datetime.datetime.now().isoformat()
        self.client.publish(
            f"{self._mqtt_prefix}/{self.name}/state", self.state.json())

    def move(self, target_node: types.VDA5050Node):
        if target_node.nodePosition is not None:
            # Are we still moving in the X direction?
            if abs(target_node.nodePosition.x - self.state.agvPosition.x) >= DISTANCE_THRESHOLD:
                direction = 1 if target_node.nodePosition.x > self.state.agvPosition.x else -1
                distance = min(abs(self.state.agvPosition.x - target_node.nodePosition.x),
                               self.speed * self.tick_period)
                self.state.agvPosition.x += direction * distance
                return True

            # Are we still moving in the Y direction?
            if abs(target_node.nodePosition.y - self.state.agvPosition.y) >= DISTANCE_THRESHOLD:
                direction = 1 if target_node.nodePosition.y > self.state.agvPosition.y else -1
                distance = min(abs(self.state.agvPosition.y - target_node.nodePosition.y),
                               self.speed * self.tick_period)
                self.state.agvPosition.y += direction * distance
                return True

            # Are we still moving in the theta direction?
            if abs(target_node.nodePosition.theta - self.state.agvPosition.theta) > 0.01:
                if target_node.nodePosition.theta > self.state.agvPosition.theta:
                    direction = 1
                else:
                    direction = -1
                delta = min(abs(self.state.agvPosition.theta - target_node.nodePosition.theta),
                            self.speed * self.tick_period)
                self.state.agvPosition.theta += direction * delta
                return True

        # We have reached the target node
        if self._current_action_id == 0 and not self.action_server_triggered:
            self.logger.info("Reached node %s", target_node.nodeId)
            self.state.nodeStates.pop(0)
            self.state.lastNodeSequenceId = target_node.sequenceId
            self.state.lastNodeId = target_node.nodeId
            if self.state.edgeStates:
                self.state.edgeStates.pop(0)
        return False

    def execute_order(self):
        # Do nothing if there is no order
        if self.order is None:
            return

        # Do nothing if we have already completed the current order
        order_size = len(self.order.nodes)
        if self._current_node >= order_size:
            return

        # Do nothing if this mission has already failed
        for error in self.state.errors:
            if error.errorLevel == types.VDA5050ErrorLevel.FATAL:
                return

        # Fail if we have reached the failure period
        if self.time_to_next_failure == 0 and self.failure_period > 0:
            e_level = types.VDA5050ErrorLevel.FATAL
            if self.fail_as_warning:
                e_level = types.VDA5050ErrorLevel.WARNING

            self.state.errors.append(
                types.VDA5050Error(errorLevel=e_level,
                                   errorReferences=[types.VDA5050ErrorReference(
                                       referenceKey="node_id",
                                       referenceValue=self.order.nodes[self._current_node].nodeId)],
                                   errorDescription="Failure period reached"))

            # Fail if FATAL, but keep going on WARNING
            if e_level == types.VDA5050ErrorLevel.FATAL:
                self.logger.info("failed mission %s", self.order.orderId)
                self.update_task_duration()
                return

        # Check if the cancel order instant action is triggered
        if self._cancel_order_action_server.triggered:
            self.logger.info("cancel order %s", self.order.orderId)
            self.state.nodeStates = []
            self.state.edgeStates = []
            for action_state in self.state.actionStates:
                if action_state.actionId == self._cancel_order_action_server.action_id:
                    action_state.actionStatus = types.VDA5050ActionStatus.FINISHED
                elif action_state.actionStatus is not types.VDA5050ActionStatus.FINISHED:
                    action_state.actionStatus = types.VDA5050ActionStatus.FAILED
            self._cancel_order_action_server.reset()
            self.update_task_duration()
            return

        # Check if teleop is triggered
        if self.pause_order:
            return

        # Get the next node we are trying to get to
        # To simulate Mission Client behavior, ignore nodePosition of first node
        target_node = self.order.nodes[self._current_node]
        if self._current_node > 0 and self.move(target_node):
            return

        # Check if this node contains actions
        if self._current_action_id < len(target_node.actions):
            target_action = target_node.actions[self._current_action_id]
            action_server = self.get_action_server(target_action.actionType)
            # Check if the server is triggered
            if action_server.triggered:
                action_server.update_status()
                if action_server.finished:
                    self.logger.info("Finished action %s",
                                     target_action.actionId)
                    self._current_action_id += 1
                    self.update_action_state(target_action.actionId,
                                             types.VDA5050ActionStatus.FINISHED)
                    action_server.reset()
                else:
                    if action_server.failed:
                        self.state.errors.append(
                            types.VDA5050Error(errorLevel=types.VDA5050ErrorLevel.FATAL,
                                               errorReferences=[types.VDA5050ErrorReference(
                                                   referenceKey="action_id",
                                                   referenceValue=target_action.actionId)],
                                               errorDescription="Action failure"))
                        action_server.reset()
                        self.update_task_duration()
                    self.update_action_state(target_action.actionId,
                                             action_server.get_status)
            else:
                # Start action server
                action_server.start(target_action.param_dict)

        else:
            self._current_action_id = 0
            self._current_node += 1

        # Check if the current mission is completed
        if self._current_node == order_size:
            self.update_task_duration()

    def get_action_server(self, action_type: str):
        if action_type == types.NVActionType.LOAD_MAP.value:
            return self._map_load_action_server
        elif action_type == types.NVActionType.PAUSE_ORDER.value:
            return self._teleop_action_server
        elif action_type == types.NVActionType.DOCK_ROBOT.value:
            return self._docking_action_server
        return self._dummy_action_server

    def update_task_duration(self):
        self._metric["duration"] = round(
            time.time() - self._metric["start_time"], 2)
        self._metrics.append(copy.copy(self._metric))
        self._metric = {}
        self._save_metrics = True
        self.order = None

    def update_action_state(self, action_id, action_status):
        for action_state in self.state.actionStates:
            if action_state.actionId == action_id:
                action_state.actionStatus = action_status
                break

    def update(self):
        self.execute_order()
        self.publish_state()
        if self._save_metrics and self._metrics_dir:
            with open(f"{self._metrics_dir}/{self.name}.json", "w+",
                      encoding="utf-8") as json_file:
                json.dump(self._metrics, json_file, indent=2)
            self._save_metrics = False

    def send_order(self, order: types.VDA5050Order):
        self.logger.info("Got order %s", order.orderId)
        new_order = True
        if self.order is not None:
            new_order = self.order.orderId != order.orderId
        self.order = copy.copy(order)

        self.state.orderId = self.order.orderId
        self.state.orderUpdateId = self.order.orderUpdateId
        self.state.headerId = self.order.headerId
        self.state.timestamp = datetime.datetime.now().isoformat()
        self.state.version = self.order.version

        # If this is a new order, reset all the node states & edge states
        if new_order:
            if self.failure_period:
                self.time_to_next_failure = \
                    (self.time_to_next_failure - 1) % self.failure_period
            self.state.errors = []
            self.state.nodeStates = []
            self.state.actionStates = []
            for node in self.order.nodes:
                self.state.nodeStates += [node.to_node_state()]
                self.state.actionStates += [types.VDA5050ActionState(actionId=action.actionId,
                                                                     actionType=action.actionType)
                                            for action in node.actions]
            self.state.edgeStates = [edge.to_edge_state()
                                     for edge in self.order.edges]
            self._current_node = 0
            self._current_action_id = 0
            self.state.lastNodeId = ""
            self._metric = {}
            self._metric["mission_id"] = order.orderId
            self._metric["start_time"] = time.time()
        self.publish_state()

    def send_instant_action(self, instant_actions: types.VDA5050InstantActions):
        self.logger.info("Got an instant action")
        current_action_ids = [
            action_state.actionId for action_state in self.state.actionStates]
        for action in instant_actions.instantActions:
            # Don't append any existing instant actions
            if action.actionId in current_action_ids:
                continue

            self.state.actionStates += [types.VDA5050ActionState(actionId=action.actionId,
                                                                 actionType=action.actionType)]
            if action.actionType == types.VDA5050InstantActionType.CANCEL_ORDER:
                self._cancel_order_action_server.set_action_id(action.actionId)
                self._cancel_order_action_server.update_status(
                    types.VDA5050ActionStatus.RUNNING)
                self.logger.info("Running %s instant action",
                                 action.actionType)

            elif action.actionType == types.NVInstantActionType.START_TELEOP:
                self.pause_order = True
                self.state.actionStates[-1].actionStatus = types.VDA5050ActionStatus.FINISHED
                self.publish_state()
                self.logger.info("Finished %s Teleop", action.actionType)

            elif action.actionType == types.NVInstantActionType.STOP_TELEOP:
                self.pause_order = False
                self.state.actionStates[-1].actionStatus = types.VDA5050ActionStatus.FINISHED
                self.publish_state()
                self.logger.info("Finished %s Teleop", action.actionType)


def robot_parser(spec: str) -> RobotInit:
    params = spec.split(",")
    map_id, theta, failure_period, battery = "map", "0", "0", "0"
    manufacturer, serial_number = "", ""
    if len(params) == 3:
        name, x, y = params
    elif len(params) == 4:
        name, x, y, theta = params
    elif len(params) == 5:
        name, x, y, theta, map_id = params
    elif len(params) == 6:
        name, x, y, theta, map_id, failure_period = params
    elif len(params) == 7:
        name, x, y, theta, map_id, failure_period, battery = params
    elif len(params) == 9:
        name, x, y, theta, map_id, failure_period, battery, manufacturer, serial_number = params
    else:
        raise argparse.ArgumentTypeError("""Robot spec must be of the form \"name,x,y\",
                                         \"name,x,y,theta\", \"name,x,y,theta,map_id\",
                                         \"name,x,y,theta,map_id,failure_period\", or
                                         \"name,x,y,theta,map_id,failure_period,battery\", or
                                         \"name,x,y,theta,map_id,failure_period,battery,manufacturer,
                                         serial_number\"""")
    return RobotInit(name, float(x), float(y), float(theta), map_id, int(failure_period),
                     float(battery), manufacturer, serial_number)


class Simulator:
    """Initialies robot objects, drives their state, and reacts to orders"""

    def __init__(self, robots: List[RobotInit], speed: float, mqtt_host: str = "localhost",
                 mqtt_transport: str = "tcp", mqtt_ws_path: Optional[str] = None,
                 mqtt_port: int = 1883, mqtt_prefix: str = "uagv/v2/Company",
                 tick_period: float = 0.25, metrics_dir: Optional[str] = None,
                 fail_as_warning: bool = False, log_level: str = "WARNING"):
        self.logger = logging.getLogger(LOGGING_NAME)
        self.logger.setLevel(log_level)
        logging.basicConfig(level=log_level,
                            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        self.mqtt_prefix = mqtt_prefix
        self.client = self._connect_to_mqtt(
            mqtt_host, mqtt_port, mqtt_transport, mqtt_ws_path)
        self.client.loop_start()
        self.robots = {init.name: Robot(init, self.client, speed, tick_period, mqtt_prefix,
                                        metrics_dir,
                                        fail_as_warning=fail_as_warning) for init in robots}
        self.tick_period = tick_period
        self.fail_as_warning = fail_as_warning

    def _connect_to_mqtt(self, host: str, port: int, transport: str, ws_path: Optional[str]) \
            -> mqtt_client.Client:
        client = mqtt_client.Client(transport=transport)
        if transport == "websockets" and ws_path is not None:
            client.ws_set_options(path=ws_path)
        client.on_connect = self._mqtt_on_connect
        client.on_message = self._mqtt_on_message
        connected = False
        while not connected:
            try:
                client.connect(host, port)
                connected = True
            except (ConnectionRefusedError, ConnectionResetError):
                self.logger.info(
                    "Failed to connect to mqtt broker, retrying in %s s", MQTT_RECONNECT_PERIOD)
                time.sleep(MQTT_RECONNECT_PERIOD)
            except socket.gaierror:
                self.logger.info(
                    "Could not resolve mqtt hostname %s, retrying in %s s",
                    host, MQTT_RECONNECT_PERIOD)
                time.sleep(MQTT_RECONNECT_PERIOD)
        return client

    def _mqtt_on_connect(self, client, userdata, flags, rc):
        client.subscribe(f"{self.mqtt_prefix}/+/order")
        client.subscribe(f"{self.mqtt_prefix}/+/instantActions")

    def _decode_message(self, msg, topic_name, topic_type, func_name):
        # Determine which robot the order belongs to
        match = re.match(f"{self.mqtt_prefix}/(.*)/{topic_name}", msg.topic)
        if match is None:
            return
        robot = match.groups()[0]

        # Ignore unkown robots
        if robot not in self.robots:
            self.logger.info(
                "Got %s for unrecognized robot %s", topic_name, robot)
            return

        # Attempt to decode and use the message
        try:
            func = getattr(self.robots[robot], func_name)
            func(topic_type(**json.loads(msg.payload)))
        except (json.decoder.JSONDecodeError, pydantic.error_wrappers.ValidationError) as error:
            self.logger.warning("Ignoring badly formed message: %s", error)

    def _mqtt_on_message(self, client, userdata, msg):
        # Decode messages
        self._decode_message(msg, "order", types.VDA5050Order, "send_order")
        self._decode_message(msg, "instantActions",
                             types.VDA5050InstantActions, "send_instant_action")

    def run(self):
        while True:
            time.sleep(self.tick_period)
            for robot in self.robots.values():
                robot.update()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--robots", nargs="+",
                        type=robot_parser, required=True)
    parser.add_argument("--fail_as_warning", action="store_true",
                        help="Treat failures as warnings.  Used with failure_period")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--mqtt_host", default="localhost",
                        help="The hostname of the mqtt server to connect to")
    parser.add_argument("--mqtt_port", default=1883, type=int,
                        help="The port of the mqtt server to connect to")
    parser.add_argument("--mqtt_transport", default="tcp", choices=("tcp", "websockets"),
                        help="Set transport mechanism as websockets or raw tcp")
    parser.add_argument("--mqtt_ws_path", default=None,
                        help="The path for the websocket if 'mqtt_transport' is 'websockets'")
    parser.add_argument("--mqtt_prefix", default="uagv/v2/RobotCompany",
                        help="The MQTT topic prefix")
    parser.add_argument("--tick_period", default=0.25, type=float,
                        help="The tick period of the simulator")
    parser.add_argument("--metrics_dir", default=None,
                        help="Log dir for robot metrics")
    parser.add_argument("--log_level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="The minimum level of log messages to print")
    args = parser.parse_args()
    sim = Simulator(**vars(args))
    sim.run()
