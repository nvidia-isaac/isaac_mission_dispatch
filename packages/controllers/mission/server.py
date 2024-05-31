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
import asyncio
import datetime
import json
import logging
import re
import requests  # type: ignore
import socket
import time
import threading
from typing import Any, Dict, List, Optional, Union
from collections import OrderedDict

import paho.mqtt.client as mqtt_client
import pydantic

from packages.controllers.mission import behavior_tree
import packages.controllers.mission.vda5050_types as types
import packages.database.client as db_client
from packages.utils import metrics
import cloud_common.objects as api_objects
import cloud_common.objects.mission as mission_object
import cloud_common.objects.robot as robot_object

import importlib

module_name = "internal_packages.push_data.telemetry_sender"
try:
    importlib.util.find_spec(module_name)
except ModuleNotFoundError:
    module_name = "packages.utils.telemetry_sender"

module = importlib.import_module(module_name)
TelemetrySender = getattr(module, "TelemetrySender")

# How long to wait in seconds before trying to reconnect to the mqtt broker
MQTT_RECONNECT_PERIOD = 0.5
# How long to wait in seconds before trying to reconnect to the mission database
DATABASE_RECONNECT_PERIOD = 0.5

RobotMessage = Union[api_objects.RobotObjectV1,
                     api_objects.MissionObjectV1,
                     types.VDA5050OrderInformation]


class StatusMessage(pydantic.BaseModel):
    name: str
    payload: types.VDA5050OrderInformation


class Robot:
    """Manages the mission state of a particular robot"""

    def __init__(self, name: str, db: db_client.DatabaseClient, client: mqtt_client.Client,
                 prefix: str, server: "RobotServer"):
        self._logger = logging.getLogger("Isaac Mission Dispatch")
        self._name = name
        self._mqtt_prefix = prefix
        self._messages: asyncio.Queue[RobotMessage] = asyncio.Queue()
        self._database = db
        self._robot_object: Optional[api_objects.RobotObjectV1] = None
        self._missions: OrderedDict[str,
                                    api_objects.MissionObjectV1] = OrderedDict()
        self._current_mission: Optional[api_objects.MissionObjectV1] = None
        self._current_instant_actions: OrderedDict[str,
                                                   types.VDA5050Action] = OrderedDict()
        self._mqtt_client = client
        self._robot_online_task: Optional[asyncio.Task[Any]] = None
        self._robot_server = server
        self._alive = True
        self._header_id = 0
        self._current_behavior_tree: Optional[behavior_tree.MissionBehaviorTree] = None
        self._updating_mission_from_api: bool = False
        self._charging_mission_received: bool = False
        if self._robot_server.push_telemetry:
            self._telemetry = metrics.Telemetry()
            self._telemetry_client = TelemetrySender(
                self._robot_server.telemetry_env)
        # To calculate the durition of a robot state
        self._cur_robot_state_timestamp = datetime.datetime.now()
        asyncio.get_event_loop().create_task(self.run())

    async def _try_start_mission(self):
        # Schedule a new mission if we aren't doing anything and there is one in the queue
        if self._current_mission is None and self._missions:
            self._current_mission = next(iter(self._missions.values()))

        # Cant start a new mission if there is no mission
        if self._current_mission is None:
            self.debug("Could not find a new mission to run")
            return
        # Cant start a new mission if there is no robot object
        if self._robot_object is None or \
                self._robot_object.lifecycle is not api_objects.object.ObjectLifecycleV1.ALIVE:
            return
        # Initialize behavior tree
        self._current_behavior_tree = behavior_tree.MissionBehaviorTree(
            self._current_mission)
        if not self._current_behavior_tree.create_behavior_tree():
            # In case the mission is not set correctly
            self._current_mission.status.failure_reason = \
                self._current_behavior_tree.failure_reason
            self._set_mission_state(mission_object.MissionStateV1.FAILED)
            await self.get_next_mission()
            return

        self.update_mission_from_behavior_tree()
        asyncio.get_event_loop().create_task(self._wait_mission_timeout(
            self._current_mission.timeout.total_seconds(),
            self._current_mission.name))
        await self._send_order()

    async def _send_instant_action(self, instant_action: types.VDA5050Action):
        instant_actions = types.VDA5050InstantActions(
            headerId=self._header_id,
            timestamp=datetime.datetime.now().isoformat(),
            instantActions=[instant_action])
        self._mqtt_client.publish(f"{self._mqtt_prefix}/{self._name}/instantActions",
                                  instant_actions.json())
        self._header_id += 1

    async def _send_order(self):
        if self._robot_object is None or self._robot_object.lifecycle \
            not in [api_objects.object.ObjectLifecycleV1.ALIVE,
                    api_objects.object.ObjectLifecycleV1.PENDING_DELETE]:
            return
        if self._current_mission is None or self._current_behavior_tree is None:
            return

        if self._current_behavior_tree.current_node is None:
            self.mission_info("No available order to be sent")
            return
        if isinstance(self._current_behavior_tree.current_node,
                      behavior_tree.MissionLeafNode):
            idx = self._current_behavior_tree.current_node.idx
            mission_node = self._current_mission.mission_tree[idx]

            # Notify node does not send an order to robot, everything is handled in Dispatch
            if mission_node.type == mission_object.MissionNodeType.NOTIFY and \
                    mission_node.notify is not None:
                self._process_notify_node(mission_node)
                return

            if mission_node.type == mission_object.MissionNodeType.ROUTE and \
                    mission_node.route is not None:
                order = types.VDA5050Order.from_route(mission_node.route, self._robot_object,
                                                      self._current_mission.name, idx)
                self.mission_info("Sending mission route node "
                                  f"{mission_node.name}")

            elif mission_node.type == mission_object.MissionNodeType.MOVE and \
                    mission_node.move is not None:
                order = types.VDA5050Order.from_move(mission_node.move, self._robot_object,
                                                     self._current_mission.name, idx)
                self.mission_info("Sending mission move node "
                                  f"{mission_node.name}")

            elif mission_node.type == mission_object.MissionNodeType.ACTION and \
                    mission_node.action is not None:
                order = types.VDA5050Order.from_action(mission_node.action, self._robot_object,
                                                       self._current_mission.name, idx)
                self.mission_info("Sending mission action node "
                                  f"{mission_node.name}")

            order.headerId = self._header_id
            self._header_id += 1
            order.timestamp = datetime.datetime.now().isoformat()

            self._mqtt_client.publish(
                f"{self._mqtt_prefix}/{self._name}/order", order.json())
            self.set_mission_node_state(f"{mission_node.name}",
                                        mission_object.MissionStateV1.RUNNING)

    def _update_mission_from_api(self, mission: api_objects.MissionObjectV1,
                                 message: api_objects.MissionObjectV1) -> bool:
        cancel_current_node = False
        # From POST /mission/{name}/cancel endpoint
        if mission.needs_canceled != message.needs_canceled:
            self.info(f"Cancel a {mission.status.state} mission [{message.name}]")
            mission.needs_canceled = message.needs_canceled
            return cancel_current_node

        # From DELETE /mission/{name} endpoint
        if mission.lifecycle != message.lifecycle:
            self.info(
                f"{mission.status.state} mission lifecycle is changed to {message.lifecycle}")
            mission.lifecycle = message.lifecycle
            return cancel_current_node

        # From POST /mission/{name}/update endpoint
        if message.update_nodes:
            self.info(
                f"Update mission nodes: {list(message.update_nodes.keys())}")
            for node_name, route in message.update_nodes.items():
                for n in mission.mission_tree:
                    if n.name == node_name:
                        n.route = route
                        if mission.status.node_status[node_name].state is \
                                mission_object.MissionStateV1.RUNNING:
                            # Cancel current node
                            cancel_current_node = True
                        break
        return cancel_current_node

    async def _on_mission_change(self, message: api_objects.MissionObjectV1):
        # If this is a new mission, add it to the queue
        if message.name not in self._missions:
            self.info(f"Received a new mission [{message.name}]")
            self._missions[message.name] = message
            if self._current_mission is None:
                await self._try_start_mission()
        else:  # If we've seen this mission, update it
            if self._current_mission is not None and self._current_mission.name == message.name:
                self.info(f"Update a RUNNING mission [{message.name}]")
                cancel_node_from_api = self._update_mission_from_api(
                    self._current_mission, message)
                # Delete/Cancel a running mission
                if self._current_mission.lifecycle == \
                        api_objects.object.ObjectLifecycleV1.PENDING_DELETE:
                    self._current_mission.needs_canceled = True

                if self._current_mission.needs_canceled or cancel_node_from_api:
                    self.info("Cancelling current node...")
                    action_id = f"{self._current_mission.name}-instantaction-n{self._header_id}"
                    instant_action = types.VDA5050Action(
                        actionType=types.VDA5050InstantActionType.CANCEL_ORDER,
                        actionId=action_id)
                    self.mission_info(f"Send cancel order action {action_id}")
                    await self._send_instant_action(instant_action)
                    self._current_instant_actions[action_id] = instant_action
                return

            self.info(f"Update a PENDING mission [{message.name}]")
            self._update_mission_from_api(
                self._missions[message.name], message)
            # Delete a queued mission
            if await self._robot_server.delete_pending_mission(message):
                del self._missions[message.name]
            # Cancel a queued mission
            elif message.needs_canceled:
                self._missions[message.name].status.state = mission_object.MissionStateV1.CANCELED
                self._database.update_status(self._missions[message.name])
                del self._missions[message.name]

    async def _on_robot_change(self, message: api_objects.RobotObjectV1):
        if self._robot_object is None:
            # Create robot object
            self.info("Created robot")
            self._robot_object = message
            self._header_id = 0
            self._robot_online_task = \
                asyncio.get_event_loop().create_task(self._check_robot_online())
            await self._try_start_mission()
        else:
            # Delete robot update
            if message.lifecycle == api_objects.object.ObjectLifecycleV1.PENDING_DELETE:
                if message.status.state == api_objects.robot.RobotStateV1.ON_TASK:
                    # Set mission to failure
                    self._set_mission_state(mission_object.MissionStateV1.FAILED)
                # Set the state of the robot to DELETE for RobotServer to delete
                # on the server and database side.
                self.debug(
                    "Robot is idle and delete request received, deleting robot.")
                await self._delete_robot_object()

            # Teleop update
            if (message.switch_teleop and
                    self._robot_object.status.state != robot_object.RobotStateV1.TELEOP) or \
                    (not message.switch_teleop and
                     self._robot_object.status.state == robot_object.RobotStateV1.TELEOP):
                action_id = f"instantaction-n{self._header_id}"
                action_type = types.NVInstantActionType.START_TELEOP \
                    if message.switch_teleop else types.NVInstantActionType.STOP_TELEOP
                instant_action = types.VDA5050Action(
                    actionType=action_type, actionId=action_id)
                self.mission_info(f"Sending {action_type.value} action.")
                await self._send_instant_action(instant_action)
                self._current_instant_actions[action_id] = instant_action

            # Robot object update
            self._robot_object = message

    async def _check_robot_online(self):
        if self._robot_object is None:
            return
        try:
            await asyncio.sleep(self._robot_object.heartbeat_timeout.total_seconds())
            self.info("Robot Offline")
            if not self._robot_object.status.online:
                return
            self._robot_object.status.online = False
            if self._robot_object.lifecycle is not api_objects.object.ObjectLifecycleV1.DELETED:
                self._database.update_status(self._robot_object)
        except asyncio.CancelledError:
            self.debug("Cancelled robot online check.")

    async def handle_instant_action(self, message: types.VDA5050OrderInformation):
        # Handle instant actions
        updated_instant_action_ids = []
        finished_instant_actions = []
        for action_state in message.actionStates[::-1]:
            # Iterate through all the appended instant actions
            if action_state.actionType not in (types.VDA5050InstantActionType.values() +
                                               types.NVInstantActionType.values()):
                break
            if action_state.actionId in self._current_instant_actions.keys():
                if action_state.actionStatus == types.VDA5050ActionStatus.FINISHED:
                    # Update current instant aciton dict
                    finished_instant_actions.append(
                        self._current_instant_actions.pop(action_state.actionId))
                    self.mission_info(
                        f"Finished instant action:\n {finished_instant_actions[-1]}")
                updated_instant_action_ids.append(action_state.actionId)

        # Resend instant actions if they are not in the feedback message
        for action_id, instant_action in self._current_instant_actions.items():
            if action_id not in updated_instant_action_ids:
                # Resend instant action
                await self._send_instant_action(instant_action)
                self.mission_info(
                    f"Resend {instant_action.actionType} instant action.")
        return finished_instant_actions

    async def _on_client_message(self, message: types.VDA5050OrderInformation):
        self.debug(f"[{message.orderId}] Got feedback")
        # If we have a robot, Update it with the details from the message
        if self._robot_object is not None:
            # Check if the current task to verify if robot is online still exists
            if self._robot_online_task is not None:
                # Cancel to replace with another task to update the online checking time
                self._robot_online_task.cancel()
            self._robot_online_task = \
                asyncio.get_event_loop().create_task(self._check_robot_online())
            self._robot_object.status.pose.x = message.agvPosition.x
            self._robot_object.status.pose.y = message.agvPosition.y
            self._robot_object.status.pose.theta = message.agvPosition.theta
            self._robot_object.status.pose.map_id = message.agvPosition.mapId
            if message.batteryState:
                self._robot_object.status.battery_level = message.batteryState.batteryCharge
                if message.batteryState.charging and not self._robot_object.status.state.running:
                    self._set_robot_state(
                        robot_object.RobotStateV1.CHARGING)
                    self._charging_mission_received = False
                elif (self._robot_object.status.state == robot_object.RobotStateV1.CHARGING and
                      not message.batteryState.charging):
                    self._set_robot_state(
                        robot_object.RobotStateV1.IDLE)

            if self._robot_server.mission_ctrl_url:
                request_map = (not self._robot_object.status.pose.map_id
                               and self._robot_object.status.state.can_deploy_map)
                send_charging_mission = (self._robot_object.battery.recommended_minimum
                                         and (self._robot_object.status.battery_level <=
                                              self._robot_object.battery.recommended_minimum)
                                         and not self._robot_object.status.state.running
                                         and not self._charging_mission_received)
                if request_map or send_charging_mission:
                    # Check mission control health
                    try:
                        health_response = requests.get(
                            self._robot_server.mission_ctrl_url + "/api/v1/health")
                        if health_response.status_code == 200:
                            # Send map request
                            if request_map:
                                response = requests.post(
                                    self._robot_server.mission_ctrl_url + "/api/v1/push_map",
                                    params={"robot_name": self._name})
                                if response.status_code == 200:
                                    self._set_robot_state(
                                        robot_object.RobotStateV1.MAP_DEPLOYMENT)
                                    logging.debug(
                                        "Map loading request posted successfully for robot %s",
                                        self._name)
                                else:
                                    logging.warning(
                                        "Failed to post map loading request for robot %s ",
                                        self._name)
                            if send_charging_mission:
                                response = requests.post(
                                    self._robot_server.mission_ctrl_url+"/api/v1/mission/charging",
                                    params={"robot_name": self._name})
                                if response.status_code == 200:
                                    logging.debug(
                                        "Charging mission posted successfully for robot %s",
                                        self._name)
                                    self._charging_mission_received = True
                                else:
                                    logging.warning(
                                        "Failed to post charging mission for robot %s ",
                                        self._name)
                    except requests.exceptions.ConnectionError as err:
                        # Service doesn't exist, handle accordingly
                        logging.warning(
                            "Connection error occurred: \n %s", err)
                    except requests.exceptions.HTTPError as http_err:
                        logging.warning("HTTP error occurred: \n %s", http_err)
                    except requests.exceptions.Timeout as timeout_err:
                        logging.warning(
                            "Timeout error occurred: \n %s", timeout_err)
            if not self._robot_object.status.online:
                self.info("Robot Online")
            self._robot_object.status.online = True
            if len(message.information) > 0:
                for information in message.information:
                    if information.infoType == "user_info":
                        self._robot_object.status.info_messages = \
                            json.loads(information.infoDescription)
                        break
            # Update robot unique ID
            self._robot_object.status.hardware_version = \
                robot_object.RobotHardwareVersionV1(manufacturer=message.manufacturer,
                                                    serial_number=message.serialNumber)
            if self._robot_object.lifecycle is not api_objects.object.ObjectLifecycleV1.DELETED:
                self._database.update_status(self._robot_object)

        finished_instant_actions = await self.handle_instant_action(message)
        self.update_robot_state(finished_instant_actions)

        # Make sure there is a mission to update
        if self._current_mission is None or self._current_behavior_tree is None:
            return

        # In case mission failed due to timeout
        if self._current_mission.status.state.done:
            self._set_robot_state(robot_object.RobotStateV1.IDLE)
            await self.get_next_mission()
            return

        # If the order doesn't match, ignore it
        if message.orderId.rsplit("-n", 1)[0] != str(self._current_mission.name):
            self.info(f"[{self._current_mission.name}] Got message from another mission order: "
                      f"{message.orderId}")
            await self._send_order()
            return

        prev_child_node = self._current_behavior_tree.current_node.name
        self.update_mission_state(message, finished_instant_actions)

        # Resend node requested by the user
        if self._updating_mission_from_api:
            self.mission_info(f"Resend the updated mission node {prev_child_node}: "
                              f"{self._current_behavior_tree.current_node.name}")
            await self._send_order()
            self._updating_mission_from_api = False

        # If current node is updated, then send a new order
        if prev_child_node != self._current_behavior_tree.current_node.name:
            self.mission_info(f"Update node from {prev_child_node} to "
                              f"{self._current_behavior_tree.current_node.name}")
            await self._send_order()

        if self._current_mission.status.state.done:
            await self.post_mission_completion()

    async def post_mission_completion(self):
        # Delete a completed/failure mission
        if self._current_mission is None:
            return
        await self._robot_server.delete_pending_mission(self._current_mission)
        # Set robot to idle
        self._set_robot_state(robot_object.RobotStateV1.IDLE)
        await self.get_next_mission()

    async def get_next_mission(self):
        if self._current_mission is None:
            return
        del self._missions[self._current_mission.name]
        self._current_mission = None
        # Check to see if a robot is pending delete
        if self._robot_object is not None and \
                self._robot_object.lifecycle == \
                api_objects.object.ObjectLifecycleV1.PENDING_DELETE:
            await self._delete_robot_object()
        else:
            await self._try_start_mission()

    async def _wait_mission_timeout(self, timeout: float, name: str):
        await asyncio.sleep(timeout)
        # Check to see if the mission that launched this thread is still running
        if (self._current_mission is None) or (self._robot_object is None):
            return

        if name == self._current_mission.name and \
                self._current_mission.status.state == mission_object.MissionStateV1.RUNNING:
            # In case there is no response from the client
            if await self._robot_server.delete_pending_mission(self._current_mission):
                return
            self._current_mission.status.failure_reason = "Mission timed out"
            self._set_mission_state(mission_object.MissionStateV1.FAILED)
            self._set_robot_state(robot_object.RobotStateV1.IDLE)

    async def _delete_robot_object(self):
        if self._robot_object is not None:
            self._robot_object.lifecycle = api_objects.object.ObjectLifecycleV1.DELETED
            self._alive = False
            if self._robot_online_task is not None:
                self._robot_online_task.cancel()
            await self._robot_server.delete_robot(self._name)

    def update_mission_node_state(self, message: types.VDA5050OrderInformation,
                                  finished_instant_actions: List[types.VDA5050Action])\
            -> mission_object.MissionStateV1:
        # Update mission state from robot client
        if self._current_mission is None:
            return mission_object.MissionStateV1.PENDING
        mission_node_index = int(message.orderId.rsplit("-n", 1)[1])
        current_mission_node = self._current_mission.mission_tree[mission_node_index]
        # If the last visited node is empty, this is the first order the robot has ran
        if message.lastNodeId == "":
            current_order_node_id = 0
        else:
            current_order_node_id = message.lastNodeSequenceId + 2

        node_state = self._current_mission.status.node_status[str(
            current_mission_node.name)].state
        if current_mission_node.type == mission_object.MissionNodeType.ROUTE and \
                current_mission_node.route is not None:
            if current_order_node_id == current_mission_node.route.size * 2 + 2:
                node_state = mission_object.MissionStateV1.COMPLETED
        elif current_mission_node.type == mission_object.MissionNodeType.MOVE and \
                current_mission_node.move is not None and current_order_node_id == 1 * 2 + 2:
            node_state = mission_object.MissionStateV1.COMPLETED
        # TODO(Nico): fix the action states index
        elif current_mission_node.type == mission_object.MissionNodeType.ACTION:
            if message.actionStates[0].actionStatus == types.VDA5050ActionStatus.FINISHED:
                node_state = mission_object.MissionStateV1.COMPLETED
            elif message.actionStates[0].actionStatus == types.VDA5050ActionStatus.FAILED:
                node_state = mission_object.MissionStateV1.FAILED
            # Check if this is a teleop action node
            elif message.actionStates[0].actionType == types.NVActionType.PAUSE_ORDER and \
                self._robot_object is not None and \
                    self._robot_object.status.state != robot_object.RobotStateV1.TELEOP:
                self._set_robot_state(robot_object.RobotStateV1.TELEOP)
                self.mission_info("Switch to teleop")
        # Check if there is an instant order cancellation feedback
        for finished_instant_action in finished_instant_actions:
            if finished_instant_action.actionType == types.VDA5050InstantActionType.CANCEL_ORDER:
                node_state = mission_object.MissionStateV1.CANCELED
                break

        if self.get_mission_errors(message):
            self.warning("Fatal Errors present, failing mission")
            node_state = mission_object.MissionStateV1.FAILED
        # Set mission node state based on update from robot client message
        self.set_mission_node_state(str(current_mission_node.name), node_state)
        return node_state

    def get_mission_errors(self, message: types.VDA5050OrderInformation):
        fatal_errors = False
        if len(message.errors) == 0:
            return False
        for error in message.errors:
            # Skip warnings
            if error.errorLevel != types.VDA5050ErrorLevel.FATAL:
                continue
            fatal_errors = True
            for error_reference in error.errorReferences:
                if error_reference.referenceKey in \
                        ["node_id", "nodeId", "action_id", "actionId"]:
                    mission_node_id = \
                        error_reference.referenceValue.rsplit(
                            "-n")[-1].rsplit("-s")[0]
                    try:
                        mission_node = int(mission_node_id)
                    except ValueError:
                        continue
                    if self._current_mission is not None and \
                            mission_node < len(self._current_mission.mission_tree):
                        (self._current_mission.status.node_status[
                            str(self._current_mission.mission_tree[mission_node].name)].error_msg) \
                            = error.errorDescription
                        self._current_mission.status.failure_reason = "\n".join(
                            error.errorDescription for error in message.errors)
        return fatal_errors

    def update_mission_from_behavior_tree(self):
        # update mission state from behavior tree
        if self._current_behavior_tree is None or self._current_mission is None:
            return
        # Record the old status and store the new status
        previous_mission_status = self._current_mission.status.copy(deep=True)
        # Update mission status
        self._current_behavior_tree.update()
        self._current_mission.status.current_node = self._current_behavior_tree.current_node.idx
        current_state = behavior_tree.tree2mission_state(
            self._current_behavior_tree.status)
        mission_state_updated = self._set_mission_state(current_state)
        # In case mission node status get updated but mission state remains the same
        if not mission_state_updated and previous_mission_status != self._current_mission.status:
            self.info(
                f"update mission node: {self._current_mission.status.current_node}")
            self._database.update_status(self._current_mission)

    def update_robot_state(self, finished_instant_actions: List[types.VDA5050Action]):
        """ Update robot states after teleop is finished

        Args:
            finished_instant_actions (List[types.VDA5050Action]): All the completed instant actions
        """
        # Check if there is an instant teleop feedback
        for finished_instant_action in finished_instant_actions:
            if finished_instant_action.actionType == types.NVInstantActionType.START_TELEOP:
                self._set_robot_state(robot_object.RobotStateV1.TELEOP)
                self.mission_info("Switch to teleop")
            else:
                resume_robot_state = robot_object.RobotStateV1.ON_TASK \
                    if self._current_mission else robot_object.RobotStateV1.IDLE
                self._set_robot_state(resume_robot_state)
                self.mission_info("Stop teleop")
            return

    def update_mission_state(self, message: types.VDA5050OrderInformation,
                             finished_instant_actions: List):
        # Update mission state from both robot feedback and behavior tree
        # Do nothing if there is no mission
        if (self._current_mission is None) or (self._robot_object is None) or \
                (self._current_behavior_tree is None):
            return

        node_state = self.update_mission_node_state(
            message, finished_instant_actions)
        if node_state == mission_object.MissionStateV1.CANCELED:
            if self._current_mission.needs_canceled:
                self._set_mission_state(mission_object.MissionStateV1.CANCELED)
            else:
                self._updating_mission_from_api = True
            return

        self.update_mission_from_behavior_tree()

    async def run(self):
        while self._alive:
            message = await self._messages.get()
            # If this is a robot object
            if isinstance(message, api_objects.RobotObjectV1):
                await self._on_robot_change(message)
            elif isinstance(message, api_objects.MissionObjectV1):
                await self._on_mission_change(message)
            elif isinstance(message, types.VDA5050OrderInformation):
                await self._on_client_message(message)

    async def send_message(self, message):
        await self._messages.put(message)

    def info(self, message: str):
        self._logger.info(
            "[Isaac Mission Dispatch] | INFO: [%s] %s", self._name, message)

    def mission_info(self, message: str):
        if self._current_mission is not None:
            mission = "Mission ID - " + self._current_mission.name
        else:
            mission = "None"
        self._logger.info("[Isaac Mission Dispatch] | INFO: [%s] [%s] %s",
                          self._name, mission, message)

    def debug(self, message: str):
        self._logger.debug(
            "[Isaac Mission Dispatch] | DEBUG: [%s] %s", self._name, message)

    def warning(self, message: str):
        self._logger.warning(
            "[Isaac Mission Dispatch] | WARNING: [%s] %s", self._name, message)

    def _set_robot_state(self, state: robot_object.RobotStateV1):
        if self._robot_object is None or state == self._robot_object.status.state:
            return
        self.info(f"Robot state: {self._robot_object.status.state} -> {state}")
        if self._robot_server.push_telemetry:
            prev_state_timestamp = self._cur_robot_state_timestamp
            self._cur_robot_state_timestamp = datetime.datetime.now()
            duration = (self._cur_robot_state_timestamp -
                        prev_state_timestamp).total_seconds()
            robot_metrics = {
                f"{self._robot_object.status.state.value}.duration": duration}
            self._telemetry.add_kpi(
                self._robot_object.name, robot_metrics, metrics.Timeframe.ROBOT)
            self._telemetry_client.send_telemetry(self._telemetry.get_kpis_by_frequency(
                metrics.Timeframe.ROBOT))
        self._robot_object.status.state = state
        self._database.update_status(self._robot_object)

    def _set_mission_state(self, state: mission_object.MissionStateV1):
        if self._current_mission is None or state == self._current_mission.status.state:
            return False
        self.mission_info(
            f"Mission state: {self._current_mission.status.state} -> {state}")
        self._current_mission.status.state = state
        self._current_mission.status.node_status["root"].state = state
        if state == mission_object.MissionStateV1.RUNNING:
            # If the mission just moved to RUNNING, set the start timestamp
            if self._current_mission.status.start_timestamp is None:
                self._current_mission.status.start_timestamp = datetime.datetime.now()
                self._set_robot_state(robot_object.RobotStateV1.ON_TASK)
                self.mission_info(
                    f"Mission started at {self._current_mission.status.start_timestamp}")
        elif state.done:
            self._current_mission.status.end_timestamp = datetime.datetime.now()
            # If the mission just moved to COMPLETED, record the end timestamp
            if state == mission_object.MissionStateV1.COMPLETED:
                self.mission_info(
                    f"Mission completed at {self._current_mission.status.end_timestamp}")
            # If the mission just moved to CANCELED, record the end timestamp
            elif state == mission_object.MissionStateV1.CANCELED:
                self.mission_info(
                    f"Mission cancelled at {self._current_mission.status.end_timestamp}")
            # If the mission just moved to FAILED, record the reason and end timestamp
            elif state == mission_object.MissionStateV1.FAILED:
                self.mission_info(
                    f"Mission failed at {self._current_mission.status.end_timestamp}")
                self.mission_info(
                    f"Failure reason: {self._current_mission.status.failure_reason}")

            if self._robot_server.push_telemetry:
                telem = {}  # type: Dict[str, Union[int, str]]
                telem[f"{state}"] = 1
                telem["mission_id"] = self._current_mission.name

                self._telemetry.add_kpi(
                    "mission_fate",
                    telem,
                    metrics.Timeframe.MISSION)
                self._telemetry_client.send_telemetry(
                    self._telemetry.get_kpis_by_frequency(
                        metrics.Timeframe.MISSION))
                self._telemetry.clear_frequency(metrics.Timeframe.MISSION)

        if self._current_mission.status.start_timestamp is not None and \
                self._current_mission.status.end_timestamp is not None:
            self.mission_info("Mission duration: "
                              f"""{self._current_mission.status.end_timestamp -
                               self._current_mission.status.start_timestamp}""")
        self._database.update_status(self._current_mission)
        return True

    def set_mission_node_state(self, node_name: str, state: mission_object.MissionStateV1):
        if self._current_mission is None:
            return
        previous_state = self._current_mission.status.node_status[node_name].state
        if previous_state == state:
            return
        self.mission_info(f"Node {node_name}: {previous_state} -> {state}")
        self._current_mission.status.node_status[node_name].state = state

    def _process_notify_node(self, mission_node):
        self.set_mission_node_state(f"{mission_node.name}",
                                    mission_object.MissionStateV1.RUNNING)
        retries = 0
        while retries <= 3:
            response = requests.post(url=mission_node.notify.url,
                                     json=mission_node.notify.json_data,
                                     timeout=mission_node.notify.timeout)
            if response.status_code == 200:
                self.set_mission_node_state(f"{mission_node.name}",
                                            mission_object.MissionStateV1.COMPLETED)
                break
            elif response.status_code in [408, 425, 429, 500, 502, 503, 504]:
                self.mission_info(
                    f"Notify: {response.status_code} received, retrying")
                retries += 1
            else:
                self.set_mission_node_state(f"{mission_node.name}",
                                            mission_object.MissionStateV1.FAILED)
                break
        if retries > 3:
            self.set_mission_node_state(f"{mission_node.name}",
                                        mission_object.MissionStateV1.FAILED)

        # Since Notify does not send an order, there is no feedback from robot, so we
        # need to trigger update here
        self.update_mission_from_behavior_tree()

    @property
    def robot_object(self) -> Optional[robot_object.RobotObjectV1]:
        return self._robot_object


class RobotServer:
    """Handles sending missions to robots using the VDA5050 protocol"""

    def __init__(self, mqtt_host: str = "localhost", mqtt_port: int = 1883,
                 mqtt_transport: str = "tcp", mqtt_ws_path: Optional[str] = None,
                 mqtt_prefix: str = "uagv/v2/RobotCompany",
                 database_url: str = "http://localhost:5000",
                 mission_ctrl_url: Optional[str] = None, push_telemetry: bool = False,
                 telemetry_env: str = "DEV"):
        """Initializes a RobotServer object by starting threads for mqtt and for the robot/mission
        database watchers
        Args:
            mqtt_host: The hostname for the mqtt client to connect to
            mqtt_port: The port for the mqtt client to connect to
            mqtt_prefix: The prefix to add to all VDA5050 mqtt topics
            databae_url: The url where the database REST API is hosted
        """
        self._logger = logging.getLogger("Isaac Mission Dispatch")

        # Save parameters to use later
        self._mqtt_prefix = mqtt_prefix

        # Connect to the db
        self._database = db_client.DatabaseClient(database_url)

        # Create queues to propogate changes to the main thread
        self._event_loop = asyncio.get_event_loop()
        self._mission_changes: asyncio.Queue[api_objects.MissionObjectV1] = asyncio.Queue(
        )
        self._robot_changes: asyncio.Queue[api_objects.RobotObjectV1] = asyncio.Queue(
        )
        self._mqtt_messages: asyncio.Queue[StatusMessage] = asyncio.Queue()

        # Launch threads to listen for updates to robot / mission objects
        mission_update_args = (
            api_objects.MissionObjectV1, self._mission_changes)
        self._mission_update_thread = threading.Thread(group=None, target=self._watch_changes,
                                                       args=mission_update_args)
        self._mission_update_thread.daemon = True
        robot_update_args = (api_objects.RobotObjectV1, self._robot_changes)
        self._robot_update_thread = threading.Thread(group=None, target=self._watch_changes,
                                                     args=robot_update_args)
        self._robot_update_thread.daemon = True

        # Connect to MQTT
        self._mqtt_client = \
            self._connect_to_mqtt(mqtt_host, mqtt_port,
                                  mqtt_transport, mqtt_ws_path)

        # The robot objects
        self._robots: Dict[str, Robot] = {}

        # Mission control
        self.mission_ctrl_url = mission_ctrl_url
        self.push_telemetry = push_telemetry
        self.telemetry_env = telemetry_env

    def _enqueue(self, queue, obj):
        asyncio.run_coroutine_threadsafe(queue.put(obj), self._event_loop)

    def _mqtt_on_connect(self, client, userdata, flags, rc):
        client.subscribe(f"{self._mqtt_prefix}/+/state")

    def _mqtt_on_message(self, client, userdata, msg):
        match = re.match(f"{self._mqtt_prefix}/(.*)/state", msg.topic)
        if match is None:
            self.warning(
                f"Got message from unrecognized topic \"{msg.topic}\"")
            return
        robot = match.groups()[0]
        self._enqueue(self._mqtt_messages, StatusMessage(name=robot,
                                                         payload=json.loads(msg.payload)))

    def _connect_to_mqtt(self, host: str, port: int, transport: str, ws_path: Optional[str]) -> \
            mqtt_client.Client:
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
                self.warning("Failed to connect to mqtt broker, retrying in "
                             f"{MQTT_RECONNECT_PERIOD}s")
                time.sleep(MQTT_RECONNECT_PERIOD)
            except socket.gaierror:
                self.warning(f"Could not resolve mqtt hostname {host}, retrying in "
                             f"{MQTT_RECONNECT_PERIOD}s")
                time.sleep(MQTT_RECONNECT_PERIOD)
        return client

    async def stop(self):
        loop = asyncio.get_event_loop()
        loop.stop()

    def _watch_changes(self, obj: Any, queue: asyncio.Queue):
        while True:
            try:
                for update in self._database.watch(obj):
                    self.debug(f"Watch object update: {obj.get_alias()}")
                    self._enqueue(queue, update)
            except requests.exceptions.ConnectionError:
                self.warning("Failed to connect to mission-database, retrying in "
                             f"{DATABASE_RECONNECT_PERIOD}")
                time.sleep(DATABASE_RECONNECT_PERIOD)
            # Force the whole program to exit if a database crashes
            except Exception as err:  # pylint: disable=broad-except
                self.warning(f"Exit: {err}")
                self._mqtt_client.loop_stop()
                asyncio.run_coroutine_threadsafe(self.stop(), self._event_loop)

    async def _handle_robot_changes(self):
        while True:
            robot = await self._robot_changes.get()
            # Ignore deleted robot object
            if robot.lifecycle == \
                    api_objects.object.ObjectLifecycleV1.DELETED:
                continue
            # Robots being deleted may not have a name
            if hasattr(robot, "name"):
                if robot.name not in self._robots:
                    self.debug(f"Got robot from database {robot.name}")
                    self._robots[robot.name] = Robot(robot.name, self._database,
                                                     self._mqtt_client, self._mqtt_prefix, self)
                await self._robots[robot.name].send_message(robot)

    async def _handle_mission_changes(self):
        while True:
            mission = await self._mission_changes.get()

            # Ignore deleted mission object
            if mission.lifecycle == \
                    api_objects.object.ObjectLifecycleV1.DELETED:
                continue

            # Ignore missions that are already done
            if mission.status.state.done:
                # Delete completed mission
                await self.delete_pending_mission(mission)
                continue

            # Put the mission into the queue for the correct robot object
            if mission.robot not in self._robots:
                self.debug(f"Got new mission from database {mission.name}")
                self._robots[mission.robot] = Robot(mission.robot, self._database,
                                                    self._mqtt_client, self._mqtt_prefix, self)
            await self._robots[mission.robot].send_message(mission)

    async def _handle_mqtt_messages(self):
        while True:
            message = await self._mqtt_messages.get()
            if message.name not in self._robots:
                self.warning(
                    f"Ignoring MQTT message from unknown robot \"{message.name}\"")
                continue
            await self._robots[message.name].send_message(message.payload)

    async def _run(self):
        await asyncio.gather(
            self._handle_robot_changes(),
            self._handle_mission_changes(),
            self._handle_mqtt_messages())

    async def delete_robot(self, robot_name: str):
        robot = self._robots[robot_name]
        if robot is not None:
            properties = robot.robot_object
            if properties is not None:
                self._database.delete(
                    api_objects.RobotObjectV1, properties.name)
                del self._robots[properties.name]

    async def delete_pending_mission(self, mission: api_objects.MissionObjectV1) -> bool:
        if mission.lifecycle == \
                api_objects.object.ObjectLifecycleV1.PENDING_DELETE:
            self._database.delete(
                api_objects.MissionObjectV1, mission.name)
            self.info(f"Deleted mission {mission.name}")
            return True
        return False

    def run(self):
        # Start threads and corroutines
        self._mission_update_thread.start()
        self._robot_update_thread.start()
        self._mqtt_client.loop_start()
        self._event_loop.run_until_complete(self._run())

    def info(self, message: str):
        self._logger.info("[Isaac Mission Dispatch] | INFO: %s", message)

    def debug(self, message: str):
        self._logger.debug("[Isaac Mission Dispatch] | DEBUG: %s", message)

    def warning(self, message: str):
        self._logger.warning("[Isaac Mission Dispatch] | WARNING: %s", message)
