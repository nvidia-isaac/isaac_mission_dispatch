"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
import datetime
import enum
from typing import Any, Dict, List, Optional

import pydantic

from cloud_common.objects import common, object


class MissionNodeType(str, enum.Enum):
    SELECTOR = "selector"
    SEQUENCE = "sequence"
    ROUTE = "route"
    MOVE = "move"
    ACTION = "action"
    NOTIFY = "notify"
    CONSTANT = "constant"


class MissionStateV1(str, enum.Enum):
    """Enum defining the state of the mission."""
    # The mission has not yet been started
    PENDING = "PENDING"
    # The mission has been accepted and started by the robot
    RUNNING = "RUNNING"
    # The mission completed successfully
    COMPLETED = "COMPLETED"
    # The mission was canceled
    CANCELED = "CANCELED"
    # The mission could not be completed
    FAILED = "FAILED"

    @property
    def done(self):
        return self in (self.COMPLETED, self.FAILED, self.CANCELED)


class MissionFailureCategoryV1(str, enum.Enum):
    """Enum defining the failure type of a failed mission."""
    # The robot app indicated that the mission failed.
    ROBOT_APP = "ROBOT_APP"
    # The server stopped the mission because it was in the RUNNING state for longer than the
    # allowed timeout.
    TIMEOUT = "TIMEOUT"
    # The server stopped the mission because it could not be completed before the deadline time was
    # reached.
    DEADLINE = "DEADLINE"
    # The mission was canceled by a user.
    CANCELED = "CANCELED"


class MissionActionNodeV1(pydantic.BaseModel):
    """
    This action leaf node defines the structure of an action behavior node, including the type of
    action and any associated parameters.

    Attributes:
        action_type (str): A string that describes the specific action the robot is supposed to
                           perform. This could be any robot-specific action like 'move', 'pick',
                           etc.

        action_parameters (Dict): A dictionary that of the parameters associated with the action.
                                  These parameters provide additional details to execute the
                                  action. The dictionary is flexible to accommodate various types
                                  of actions and their unique requirements.
    """
    action_type: str = pydantic.Field(
        description="Describes an action that the robot can perform")
    action_parameters: Dict = pydantic.Field(
        {}, description="Dictionary of parameters for the specified action.")


class MissionConstantNodeV1(pydantic.BaseModel):
    """
    This class represents a constant leaf node in a mission structure. It's a simple node
    that only holds a state value indicating success or failure. When this node is
    started, it immediately resolves to the predefined state. It's useful in scenarios
    where a static outcome is needed as part of the mission flow.

    Attributes:
        success (bool): This attribute holds the state of the node. It determines what
                        state the node will resolve to when it is executed. The default
                        value is True, which means the node will resolve to a success
                        state by default. If set to False, the node will resolve to a
                        failure state. This can be useful in testing or conditional
                        branching scenarios within a mission.
    """
    success: bool = pydantic.Field(
        True, description="The node's initial state, either True or False, upon activation.")


class MissionRouteNodeV1(pydantic.BaseModel):
    """
    This route leaf node specifies a sequence of waypoints that the robot should execute.
    This class is particularly useful in defining the path a robot needs to take in terms
    of a series of Pose2D object including x, y coordinates and rotation theta.

    Attributes:
        waypoints: A list of waypoints (Pose2D objects) that the robot is supposed to navigate.
    """
    waypoints: List[common.Pose2D] = pydantic.Field(
        description="Describes a list of pose2D waypoints")

    @property
    def size(self):
        return len(self.waypoints)

    @pydantic.validator("waypoints")
    def _validate_at_least_one_waypoint(cls, value):
        if len(value) < 1:
            raise common.ICSUsageError("Number of waypoints must be >= 1")
        return value


class MissionMoveNodeV1(pydantic.BaseModel):
    """
    This move leaf node is used to define a movement command for a robot, which can include
    either linear movement, rotational movement, but not both.

    Attributes:
        distance (Optional[float]): Specifies the linear distance the robot should move.
            This value is in meters. If not specified, there is no linear movement.
        rotation (Optional[float]): Specifies the angular distance for the robot's rotation.
            This value is in radians. If not specified, there is no rotational movement.
    """
    distance: Optional[float] = pydantic.Field(
        description="The distance that robot needs to move")
    rotation: Optional[float] = pydantic.Field(
        description="The relative rotation that robot needs to move in radians")

    @pydantic.root_validator
    def validate_mission_move_node_type(cls, values):
        types = ["distance", "rotation"]
        set_types = [type for type in types if values.get(type) is not None]
        if len(set_types) != 1:
            raise common.ICSUsageError(f"Exactly one of the following must be set {types}, "
                                       f"but the following {len(set_types)} are set {set_types}")
        return values


class MissionNotifyNodeV1(pydantic.BaseModel):
    """
    This notify leaf node is used to trigger an external API call at a specified point
    in the mission flow. It includes details about the API endpoint, the data to be sent,
    and a timeout for the API call.

    Attributes:
        url (str): The URL of the API endpoint that the Dispatch system will call.
        json_data (Dict): A dictionary representing the JSON payload to be sent along
                          with the API call. This is the data that will be included in the
                          body of the request.
        timeout (int): The timeout in seconds for the API call. This specifies how long
                       the Dispatch system should wait for a response from the API before
                       timing out.
    """
    url: str = pydantic.Field(description="API endpoint to be called")
    json_data: Dict = pydantic.Field({}, description="JSON payload")
    timeout: int = pydantic.Field(
        30, description="Timeout in seconds for the API call")


class MissionNodeV1(pydantic.BaseModel):
    """Specifies a mission node"""
    name: Optional[str] = pydantic.Field(
        None, description="A name for the node")
    parent: str = pydantic.Field(
        "root", description="A parent for the node")
    route: Optional[MissionRouteNodeV1] = pydantic.Field(
        description="A list of poses for the robot to complete.")
    move: Optional[MissionMoveNodeV1] = pydantic.Field(
        description="A distance or relative rotation for the robot to complete.")
    action: Optional[MissionActionNodeV1] = pydantic.Field(
        description="An action for the robot to complete.")
    notify: Optional[MissionNotifyNodeV1] = pydantic.Field(
        description="An API for Dispatch to call.")
    selector: Optional[Dict] = pydantic.Field(
        None, description="When started, this node will start its first child. If the child \
            currently running returns FAILED, start the next child. If all children fail, \
            this node returns FAILURE. If any child succeeds, this node immediately returns \
            SUCCESS.")
    sequence: Optional[Dict] = pydantic.Field(
        None, description="When started, this node will start its first child. If the child \
            currently running returns SUCCESS, start the next child. If all children succeed, \
            this node returns SUCCESS. If any child fails, this node immediately returns FAILURE.")
    constant: Optional[MissionConstantNodeV1] = pydantic.Field(
        description="A boolean describing the whether the node status should be a success \
            or failure when started")

    @pydantic.root_validator
    def validate_mission_node_type(cls, values):
        types = [e.value for e in MissionNodeType]
        set_types = [type for type in types if values.get(type) is not None]
        if len(set_types) != 1:
            raise common.ICSUsageError(f"Exactly one of the following must be set {types}, "
                                       f"but the following {len(set_types)} are set {set_types}")
        return values

    @property
    def type(self):
        dict_set = self.dict(exclude_unset=True, exclude_none=True)
        for node_type in MissionNodeType:
            if node_type.value in dict_set:
                return node_type

    @classmethod
    def get_field_description(cls, field):
        return cls.__fields__[field].field_info.description

    @classmethod
    def get_supported_behaviors(cls):
        behaviors = []
        behavior_class_map = {
            "route": MissionRouteNodeV1,
            "move": MissionMoveNodeV1,
            "action": MissionActionNodeV1,
            "notify": MissionNotifyNodeV1,
            "constant": MissionConstantNodeV1
        }
        for k, v in behavior_class_map.items():
            behaviors.append(
                {"name": k, "params": list(getattr(v, "__fields__", {}).keys()),
                 "description": v.__doc__})
        behaviors.append({"name": "sequence", "params": [],
                          "description": cls.get_field_description("sequence")})
        behaviors.append({"name": "selector", "params": [],
                          "description": cls.get_field_description("selector")})
        return behaviors


class MissionSpecV1(pydantic.BaseModel):
    """Specifies which robot the mission is assigned to and which orders must be completed for
    the mission."""
    robot: str = pydantic.Field(
        description="The name of the robot that this mission is assigned to.")
    mission_tree: List[MissionNodeV1] = pydantic.Field(
        description="A list of nodes (tasks) for the robot to complete.")
    timeout: datetime.timedelta = pydantic.Field(
        datetime.timedelta(seconds=300),
        description="How long the mission is allowed to run before giving up.")
    deadline: Optional[datetime.datetime] = pydantic.Field(
        description="When the mission must complete by before it is canceled.")
    needs_canceled: bool = pydantic.Field(
        False, description="Marker for whether the mission is requested to be canceled"
    )
    update_nodes: Optional[Dict[str, MissionRouteNodeV1]] = pydantic.Field(
        None, description="Nodes need to be updated")

    @pydantic.validator("mission_tree")
    def _validate_at_least_one_node(cls, value):
        if len(value) < 1:
            raise common.ICSUsageError("Number of nodes must be >= 1")

        name_set = set(["root"])
        for i, node in enumerate(value):
            # If no name is provided, assign a default
            if node.name is None:
                node.name = str(i)
            # Make sure all names are unique
            if node.name in name_set:
                raise common.ICSUsageError(
                    f"MissionNode name {node.name} is repeated. All MissionNode names"
                    "must be unique.")
            # Make sure the parent appears and it is before the child. This ensures there are no
            # cycles
            if node.parent not in name_set:
                raise common.ICSUsageError(
                    f"MissionNode \"{node.name}\" has parent \"{node.parent}\" which"
                    " does not appear before it in the mission_tree.")

            name_set.add(node.name)

        return value


class MissionNodeStatusV1(pydantic.BaseModel):
    """The status of a given node in the mission tree"""
    state: MissionStateV1 = MissionStateV1.PENDING
    error_msg: Optional[str] = None


class MissionStatusV1(pydantic.BaseModel):
    """Specifies the progress made on the mission so far."""
    state: MissionStateV1 = pydantic.Field(
        MissionStateV1.PENDING, description="The completion status of the mission.")
    current_node: int = pydantic.Field(
        0, description="The index of the order the robot is currently working on. A value of 0 \
                        means the robot is working on the first node")
    node_status: Dict[str, MissionNodeStatusV1] = pydantic.Field(
        {}, description="The state and optional failure/success message of all tree nodes.")
    task_status: Dict[str, int] = pydantic.Field(
        {}, description="Tracks the current task index of a node")
    start_timestamp: Optional[datetime.datetime] = pydantic.Field(
        None, description="The timestamp of when this mission is started.")
    end_timestamp: Optional[datetime.datetime] = pydantic.Field(
        None, description="The timestamp of when this mission ended. A value of null means the \
                        mission is still pending.")
    failure_reason: Optional[str] = pydantic.Field(
        None, description="If a mission is moved to the FAILED state, this provides a human \
                           readable reason why.")
    failure_category: Optional[MissionFailureCategoryV1] = pydantic.Field(
        None, description="A enum describing the cause of the mission failure.")

    class Config:
        use_enum_value = True


class MissionQueryParamsV1(pydantic.BaseModel):
    """Specifies the supported query parameters allowed for missions"""
    state: Optional[MissionStateV1]
    started_after: Optional[datetime.datetime]
    started_before: Optional[datetime.datetime]
    robot: Optional[str]
    most_recent: Optional[int]


class MissionObjectV1(MissionSpecV1, object.ApiObject):
    """Specifies a mission, which is a list of orders, to be completed by a specific robot."""
    status: MissionStatusV1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for node in ["root"] + [node.name for node in self.mission_tree if node.name is not None]:
            if node not in self.status.node_status:
                self.status.node_status[str(node)] = MissionNodeStatusV1()

    @classmethod
    def get_alias(cls) -> str:
        return "mission"

    @classmethod
    def get_spec_class(cls) -> Any:
        return MissionSpecV1

    @classmethod
    def get_status_class(cls) -> Any:
        return MissionStatusV1

    @classmethod
    def get_methods(cls) -> List[object.ApiObjectMethod]:
        return [
            object.ApiObjectMethod(
                name="cancel", description="Marks a mission to be cancelled by mission \
                    dispatch when it is able to.", function=cls.cancel),
            object.ApiObjectMethod(
                name="update", description="This endpoint is to update the route \
                    nodes within a mission. If updates involving changes to sequence and \
                    selector nodes in the mission tree structure are necessary, please cancel \
                    the mission and submit it again with the revisions.",
                function=cls.update,
                params=Dict[str, MissionRouteNodeV1])
        ]

    @classmethod
    def get_query_params(cls) -> Any:
        return MissionQueryParamsV1

    @classmethod
    def supports_spec_update(cls) -> bool:
        return False

    @classmethod
    def default_spec(cls) -> Dict:
        return MissionSpecV1(robot="NULL",
                             mission_tree=[MissionNodeV1(sequence={})]).dict()  # type: ignore

    async def cancel(self):
        if self.status.state.done:
            if self.status.state is MissionStateV1.CANCELED:
                raise common.ICSUsageError(
                    f"Mission {self.name} is already canceled.")
            else:
                raise common.ICSUsageError(
                    f"Completed mission {self.name} can't be canceled.")
        self.needs_canceled = True
        return {"detail": f"Mission {self.name} will be canceled."}

    async def update(self, update_nodes: Dict[str, MissionRouteNodeV1]):
        if self.status.state.done:
            raise common.ICSUsageError(
                f"Mission {self.name} is finished with status {self.status.state}.")
        current_node_names = [n.name for n in self.mission_tree]
        for node_name, _ in update_nodes.items():
            if node_name not in current_node_names:
                raise common.ICSUsageError(
                    f"Node {node_name} does not exist in mission {self.name}")
            elif self.status.state is MissionStateV1.RUNNING and \
                    self.status.node_status[node_name].state.done:
                raise common.ICSUsageError(
                    f"Mission node {node_name} is finished with status \
                        {self.status.node_status[node_name].state}.")
        # Update when the nodes exist in the mission and the mission is in PENDING or RUNNING state
        self.update_nodes = update_nodes
        return update_nodes

    @staticmethod
    def get_query_map() -> Dict:
        return {
            "state": "status->>'state' = '{}'",
            "started_after": "(status->>'start_timestamp') >= '{}'",
            "started_before": "(status->>'start_timestamp') <= '{}'",
            "robot": "spec->>'robot' = '{}'",
            "most_recent": " ORDER BY (status->>'start_timestamp') DESC LIMIT {}"
        }
