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
import enum
import math
from typing import List, Optional

import pydantic

from cloud_common.objects import mission, robot, common


# Tell pylint to ignore the invalid names. We must use camelCase names because they are specified
# by VDA5050, and these classes are serailized directly to json with the member names as keys
# pylint: disable=invalid-name

class HeaderModel:
    headerId: int
    timestamp: str
    version: str
    manufacturer: str
    serialNumber: str


class VDA5050EdgeState(pydantic.BaseModel):
    edgeId: str
    sequenceId: int
    edgeDescription: str = ""
    released: bool = True


class VDA5050ActionParameter(pydantic.BaseModel):
    """Action parameters"""
    key: str
    value: str


class VDA5050ActionBlockingType(str, enum.Enum):
    # “NONE” – allows driving and other actions
    NONE = "NONE"
    # “SOFT” - allows other actions, but not driving
    SOFT = "SOFT"
    # “HARD” - is the only allowd action at that time
    HARD = "HARD"


class VDA5050InstantActionType(str, enum.Enum):
    # cancel order
    CANCEL_ORDER = "cancelOrder"
    FACTSHEET_REQUEST = "factsheetRequest"

    @classmethod
    def values(cls):
        return [member.value for member in cls]


class NVInstantActionType(str, enum.Enum):
    START_TELEOP = "startTeleop"
    STOP_TELEOP = "stopTeleop"

    @classmethod
    def values(cls):
        return [member.value for member in cls]


class NVActionType(str, enum.Enum):
    DUMMY_ACTION = "dummy_action"
    LOAD_MAP = "load_map"
    PAUSE_ORDER = "pause_order"
    DOCK_ROBOT = "dock_robot"
    GET_OBJECTS = "get_objects"


class VDA5050ActionStatus(str, enum.Enum):
    """Action status describe at which stage of the actions lifecycle the action is"""
    # Action is waiting for trigger
    WAITING = "WAITING"
    # Action was triggered, preparatory measures are initiated
    INITIALIZING = "INITIALIZING"
    # Action is running
    RUNNING = "RUNNING"
    # Action is paused by instantAction or external trigger (pause button on the robot)
    PAUSED = "PAUSED"
    # The action is finished and a result is reported via the resultDescription
    FINISHED = "FINISHED"
    # Action could not be performed for whatever reason
    FAILED = "FAILED"

    @property
    def done(self):
        return self in (self.FINISHED, self.FAILED)


class VDA5050Action(pydantic.BaseModel):
    """Action, sent from the server to the client"""
    actionType: str
    actionId: str
    blockingType: VDA5050ActionBlockingType = VDA5050ActionBlockingType.HARD
    actionParameters: List[VDA5050ActionParameter] = []
    actionDescription: str = ""

    @classmethod
    def from_mission_action(cls, action: mission.MissionActionNodeV1,
                            node_id: str, mission_node_id: int) -> "VDA5050Action":
        return VDA5050Action(
            actionType=action.action_type,
            actionId=f"{node_id}-n{mission_node_id}",
            actionParameters=[VDA5050ActionParameter(key=k, value=v)
                              for k, v in action.action_parameters.items()])

    @property
    def param_dict(self):
        return {param.key: param.value for param in self.actionParameters}


class VDA5050ActionState(pydantic.BaseModel):
    """VDA5050 Action State, sent from the client to the server"""
    actionId: str
    actionType: str = ""
    actionDescription: str = ""
    actionStatus: VDA5050ActionStatus = VDA5050ActionStatus.WAITING
    resultDescription: str = ""


class VDA5050NodePosition(pydantic.BaseModel):
    x: float
    y: float
    theta: float = 0.0
    mapId: str = ""
    mapDescription: str = ""
    allowedDeviationXY: float = 0.0
    allowedDeviationTheta: float = 0.0


class VDA5050NodeState(pydantic.BaseModel):
    nodeId: str
    sequenceId: int
    released: bool = True
    position: Optional[VDA5050NodePosition]


class VDA5050Node(pydantic.BaseModel):
    """A node to travel to, sent from the server to the client"""
    nodeId: str
    sequenceId: int
    released: bool = True
    nodePosition: Optional[VDA5050NodePosition]
    actions: List[VDA5050Action] = []
    nodeDescription: str = ""

    def to_node_state(self) -> VDA5050NodeState:
        return VDA5050NodeState(nodeId=self.nodeId, sequenceId=self.sequenceId,
                                released=self.released, position=self.nodePosition)

    @classmethod
    def from_pose2d(cls, pose: common.Pose2D, mission_id: str, sequence: int,
                    mission_node_id: int) -> "VDA5050Node":
        return VDA5050Node(
            nodeId=f"{mission_id}-n{mission_node_id}-s{sequence}",
            sequenceId=sequence,
            nodePosition=VDA5050NodePosition(
                x=pose.x, y=pose.y, theta=pose.theta, mapId=pose.map_id,
                allowedDeviationXY=pose.allowedDeviationXY,
                allowedDeviationTheta=pose.allowedDeviationTheta))

    @classmethod
    def from_robot(cls, robot_object: robot.RobotObjectV1, mission_id: str,
                   mission_node_id: int = 0, sequence: int = 0) -> "VDA5050Node":
        return VDA5050Node(
            nodeId=f"{mission_id}-n{mission_node_id}-s{sequence}",
            sequenceId=sequence,
            nodePosition={
                "x": robot_object.status.pose.x,
                "y": robot_object.status.pose.y,
                "theta": robot_object.status.pose.theta})

    @classmethod
    def from_move(cls, robot_object: robot.RobotObjectV1, move: mission.MissionMoveNodeV1,
                  mission_id: str, mission_node_id: int = 0, sequence: int = 0) -> "VDA5050Node":
        """
        Create a VDA5050Node instance based on the robot's current status and a movement command.

        Args:
        - robot_object: Instance of robot.RobotObjectV1 representing the current robot status.
        - move: Instance of mission.MissionMoveNodeV1 with the robot's movement command.
        - mission_id: String identifier of the mission.
        - mission_node_id: Integer for the node ID in the mission (default is 0).
        - sequence: Integer for the sequence number of this node in the mission (default is 0).

        Returns:
        - A VDA5050Node instance representing the robot's status after executing the move.

        This method calculates the robot's new position (x, y) and orientation after executing
        a movement command. The command can be a linear movement (distance) or a rotation. If the
        command includes a distance, it calculates the new (x, y) position based on the current
        position and orientation. If it includes a rotation, the robot's orientation is updated.
        The method then returns a VDA5050Node instance with the updated position and orientation.
        """
        # Current position and orientation of the robot
        x = robot_object.status.pose.x
        y = robot_object.status.pose.y
        theta = robot_object.status.pose.theta

        # Update position if there's a distance to move
        if move.distance:
            # The cosine function determines how much of the movement is along the x-axis.
            x = x + move.distance * math.cos(robot_object.status.pose.theta)
            # The sine function determines how much of the movement is along the y-axis.
            y = y + move.distance * math.sin(robot_object.status.pose.theta)
        # Update orientation if there's a rotation
        elif move.rotation:
            theta = theta + move.rotation

        # Create and return a new VDA5050Node with the updated position and orientation
        return VDA5050Node(
            nodeId=f"{mission_id}-n{mission_node_id}-s{sequence}",
            sequenceId=sequence,
            nodePosition={"x": x, "y": y, "theta": theta})


class VDA5050Edge(pydantic.BaseModel):
    """An edge between two nodes sent from the server to the robot"""
    edgeId: str
    sequenceId: int
    edgeDescription: str = ""
    released: bool = True
    startNodeId: str
    endNodeId: str
    actions: List[VDA5050Action] = []

    def to_edge_state(self) -> VDA5050EdgeState:
        return VDA5050EdgeState(edgeId=self.edgeId, sequenceId=self.sequenceId,
                                released=self.released)

    @classmethod
    def from_mission_order(cls, mission_id: str, sequence: int,
                           mission_node_id: int) -> "VDA5050Edge":
        return VDA5050Edge(
            edgeId=f"{mission_id}-e{sequence}",
            sequenceId=sequence,
            startNodeId=f"{mission_id}-n{mission_node_id}-s{sequence - 1}",
            endNodeId=f"{mission_id}-n{mission_node_id}-s{sequence + 1}")


class VDA5050AgvPosition(pydantic.BaseModel):
    positionInitialized: bool = True
    x: float
    y: float
    theta: float
    mapId: str = ""
    deviationRange: float = 0.0


class VDA5050Velocity(pydantic.BaseModel):
    vx: float
    vy: float
    omega: float


class VDA5050ErrorReference(pydantic.BaseModel):
    referenceKey: str
    referenceValue: str


class VDA5050ErrorLevel(str, enum.Enum):
    WARNING = "WARNING"
    FATAL = "FATAL"


class VDA5050Error(pydantic.BaseModel):
    errorReferences: List[VDA5050ErrorReference] = []
    errorDescription: str
    errorLevel: VDA5050ErrorLevel = VDA5050ErrorLevel.WARNING


class VDA5050InfoReference(pydantic.BaseModel):
    referenceKey: str
    referenceValue: str


class VDA5050Info(pydantic.BaseModel):
    infoType: str
    infoReferences: List[VDA5050InfoReference] = []
    infoDescription: str
    infoLevel: str


class VDA5050Order(pydantic.BaseModel):
    """VDA5050 Order message sent from mission server to robot"""
    headerId: int = 0
    timestamp: str = ""
    version: str = "2.0.0"
    manufacturer: str = ""
    serialNumber: str = ""
    orderId: str
    orderUpdateId: int
    nodes: List[VDA5050Node]
    edges: List[VDA5050Edge]

    @pydantic.validator("nodes")
    def _validate_at_least_one_node(cls, value):
        if len(value) < 1:
            raise common.ICSUsageError("Number of nodes must be >= 1")
        return value

    @pydantic.validator("edges")
    def _validate_node_edge_count(cls, edges, values):
        edge_count = len(edges)
        node_count = len(values.get("nodes", []))
        target_edge_count = node_count - 1
        if edge_count != target_edge_count:
            raise common.ICSUsageError(
                "There must be exactly one less edge than nodes. There are "
                f"{node_count} nodes and {edge_count} edges, but there should be "
                f"{target_edge_count} edges")
        return edges

    @classmethod
    def from_mission(cls, mission_object: mission.MissionObjectV1,
                     robot_object: robot.RobotObjectV1,
                     header_id: int,
                     timestamp: str) -> "VDA5050Order":
        # Create an initial node from the robots current position
        nodes = [VDA5050Node(
            nodeId=f"{mission_object.name}-s0-n0",
            sequenceId=0,
            position={
                "x": robot_object.status.pose.x,
                "y": robot_object.status.pose.y,
                "theta": robot_object.status.pose.theta
            })]
        edges = []
        node_sequence = 1
        for i, mission_node in enumerate(mission_object.mission_tree):
            # If this is a route mission node, add each pose in the route as a node
            if mission_node.route is not None:
                nodes += [VDA5050Node.from_pose2d(pose2d, str(mission_object.name),
                                                  j + node_sequence, i + 1) for j, pose2d
                          in enumerate(mission_node.route.waypoints)]
                edges += [VDA5050Edge.from_mission_order(str(mission_object.name),
                                                         e + node_sequence, i + 1)
                          for e in range(mission_node.route.size)]
                node_sequence += len(mission_node.route.waypoints)
            # If this is an action mission node, attach the actions to the last vda5050 node
            elif mission_node.action is not None:
                nodes[-1].actions += [VDA5050Action.from_mission_action(mission_node.action,
                                                                        nodes[-1].nodeId,
                                                                        i + 1)]
        return VDA5050Order(
            headerId=header_id,
            timestamp=timestamp,
            orderId=mission_object.name,
            orderUpdateId=0,
            nodes=nodes,
            edges=edges)

    @classmethod
    def from_route(cls, route: mission.MissionRouteNodeV1,
                   robot_object: robot.RobotObjectV1,
                   mission_id: str,
                   mission_node_id: int) -> "VDA5050Order":
        # Create an initial node from the robots current position
        nodes = [VDA5050Node.from_robot(
            robot_object, mission_id, mission_node_id)]
        edges = []
        # Add each pose in the route as a node
        if route is not None:
            nodes += [VDA5050Node.from_pose2d(pose2d, mission_id,
                                              j * 2 + 2, mission_node_id) for j, pose2d
                      in enumerate(route.waypoints)]
            edges += [VDA5050Edge.from_mission_order(mission_id,
                                                     e * 2 + 1, mission_node_id)
                      for e in range(route.size)]
        return VDA5050Order(
            orderId=f"{mission_id}-n{mission_node_id}",
            orderUpdateId=0,
            nodes=nodes,
            edges=edges)

    @classmethod
    def from_move(cls, move: mission.MissionMoveNodeV1,
                  robot_object: robot.RobotObjectV1,
                  mission_id: str,
                  mission_node_id: int) -> "VDA5050Order":
        # Create an initial node from the robots current position
        nodes = [VDA5050Node.from_robot(
            robot_object, mission_id, mission_node_id)]
        edges = []
        nodes += [VDA5050Node.from_move(robot_object,
                                        move, mission_id, mission_node_id, 2)]
        edges += [VDA5050Edge.from_mission_order(
            mission_id, 1, mission_node_id)]
        return VDA5050Order(
            orderId=f"{mission_id}-n{mission_node_id}",
            orderUpdateId=0,
            nodes=nodes,
            edges=edges)

    @classmethod
    def from_action(cls, action: mission.MissionActionNodeV1,
                    robot_object: robot.RobotObjectV1,
                    mission_id: str,
                    mission_node_id: int) -> "VDA5050Order":
        # Create an initial node from the robots current position
        nodes = [VDA5050Node.from_robot(
            robot_object, mission_id, mission_node_id)]
        # Attach the actions to a vda5050 node
        if action is not None:
            nodes[0].actions += [VDA5050Action.from_mission_action(action,
                                                                   nodes[0].nodeId,
                                                                   mission_node_id)]
        return VDA5050Order(
            orderId=f"{mission_id}-n{mission_node_id}",
            orderUpdateId=0,
            nodes=nodes,
            edges=[])


class VDA5050BatteryState(pydantic.BaseModel):
    batteryCharge: float
    batteryVoltage: Optional[float]
    batteryHealth: Optional[int]
    charging: bool
    reach: Optional[int]


class VDA5050BoundingBoxReference(pydantic.BaseModel):
    theta: Optional[int]
    x: int
    y: int
    z: int


class VDA5050LoadDimensions(pydantic.BaseModel):
    height: Optional[int]
    length: int
    width: int


class VDA5050Load(pydantic.BaseModel):
    boundingBoxReference: Optional[VDA5050BoundingBoxReference]
    loadDimensions: Optional[VDA5050LoadDimensions]
    loadId: Optional[str]
    loadPosition: Optional[str]
    loadType: Optional[str]
    weight: Optional[int]


class VDA5050OperatingMode(str, enum.Enum):
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    SEMIAUTOMATIC = "SEMIAUTOMATIC"
    SERVICE = "SERVICE"
    TEACHIN = "TEACHIN"


class VDA5050EStop(str, enum.Enum):
    AUTOACK = "AUTOACK"
    MANUAL = "MANUAL"
    NONE = "NONE"
    REMOTE = "REMOTE"


class VDA5050SafetyStatus(pydantic.BaseModel):
    eStop: VDA5050EStop = VDA5050EStop.NONE
    fieldViolation: bool = False

    @pydantic.validator("eStop", pre=True)
    def default_operating_mode(cls, v):
        if v == "":
            return VDA5050EStop.NONE
        return v


class VDA5050State(pydantic.BaseModel):
    """Feedback on the current mission and robot status from the client"""
    headerId: int
    timestamp: str
    version: str = "2.0.0"
    manufacturer: str = ""
    serialNumber: str = ""
    orderId: str = ""
    orderUpdateId: int = 0
    lastNodeId: str = ""
    lastNodeSequenceId: int = 0
    nodeStates: List[VDA5050NodeState]
    edgeStates: List[VDA5050EdgeState]
    actionStates: List[VDA5050ActionState] = []
    batteryState: Optional[VDA5050BatteryState]
    driving: bool = False
    agvPosition: Optional[VDA5050AgvPosition]
    errors: List[VDA5050Error] = []
    information: Optional[List[VDA5050Info]] = []
    distanceSinceLastNode: Optional[float] = 0.0
    loads: Optional[List[VDA5050Load]] = []
    newBaseRequest: Optional[bool] = False
    operatingMode: VDA5050OperatingMode = VDA5050OperatingMode.AUTOMATIC
    paused: Optional[bool] = False
    safetyState: VDA5050SafetyStatus
    velocity: Optional[VDA5050Velocity]
    zoneSetId: Optional[str] = ""

    @pydantic.validator("operatingMode", pre=True)
    def default_operating_mode(cls, v):
        if v == "":
            return VDA5050OperatingMode.AUTOMATIC
        return v


class VDA5050TypeSpecification(pydantic.BaseModel):
    """Describes general properties of a robot"""
    seriesName: Optional[str]
    seriesDescription: Optional[str]
    agvKinematic: Optional[str]
    agvClass: str = "CARRIER"
    maxLoadMass: Optional[float]
    localizationTypes: Optional[List[str]]
    navigationTypes: Optional[List[str]]


class VDA5050PhysicalParameters(pydantic.BaseModel):
    """Describes physical properties of a robot"""
    speedMin: Optional[float]
    speedMax: float = 1
    accelerationMax: Optional[float]
    decelerationMax: Optional[float]
    heightMin: Optional[float]
    heightMax: Optional[float]
    width: Optional[float]
    length: Optional[float]


# # # # # # # # # # # # # # # # # # # #
#                                     #
# !TODO: PAVAN                        #
# fill classes with correct fields    #
# # # # # # # # # # # # # # # # # # # #
class VDA5050ProtocolLimits(pydantic.BaseModel):
    temporary: int


class VDA5050ProtocolFeatures(pydantic.BaseModel):
    temporary: int


class VDA5050AGVGeometry(pydantic.BaseModel):
    temporary: int


class VDA5050LoadSpecification(pydantic.BaseModel):
    temporary: int


class VDA5050LocalizationParameters(pydantic.BaseModel):
    temporary: int


class VDA5050Factsheet(pydantic.BaseModel):
    """Specification information specific to each robot type"""
    headerId: int = 0
    timestamp: str = ""
    version: str = "2.0.0"
    manufacturer: str = ""
    serialNumber: str = ""
    typeSpecification: VDA5050TypeSpecification = VDA5050TypeSpecification()
    physicalParameters: VDA5050PhysicalParameters = VDA5050PhysicalParameters()
    protocolLimits: Optional[VDA5050ProtocolLimits]
    protocolFeatures: Optional[VDA5050ProtocolFeatures]
    agvGeometry: Optional[VDA5050AGVGeometry]
    loadSpecification: Optional[VDA5050LoadSpecification]
    localizationParameters: Optional[VDA5050LocalizationParameters]


class VDA5050Visualization(pydantic.BaseModel):
    """For a near real-time position and velocity update of the AGV"""
    headerId: int
    timestamp: str
    version: str = "2.0.0"
    manufacturer: str = ""
    serialNumber: str = ""
    agvPosition: Optional[VDA5050AgvPosition]
    velocity: Optional[VDA5050Velocity]


class VDA5050InstantActions(pydantic.BaseModel):
    """Instant Action"""
    headerId: int
    timestamp: str
    version: str = "2.0.0"
    manufacturer: str = ""
    serialNumber: str = ""
    instantActions: List[VDA5050Action]


class VDA5050ConnectionState(str, enum.Enum):
    CONNECTIONBROKEN = "CONNECTIONBROKEN"
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"


class VDA5050Connection(pydantic.BaseModel):
    """Connection"""
    headerId: int
    timestamp: str
    version: str = "2.0.0"
    manufacturer: str = ""
    serialNumber: str = ""
    connectionState: VDA5050ConnectionState = VDA5050ConnectionState.OFFLINE
