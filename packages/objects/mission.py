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
from typing import Any, List, Optional, Dict

import pydantic

from packages.objects import common, object


class MissionNodeType(str, enum.Enum):
    SELECTOR = "selector"
    SEQUENCE = "sequence"
    ROUTE = "route"
    ACTION = "action"
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
    """Specifies an action to be executed to by the robot"""
    action_type: str = pydantic.Field(
        description="Describes an action that the robot can perform")
    action_parameters: Dict = pydantic.Field(
        {}, description="Array of action parameter for the indicated action")


class MissionConstantNodeV1(pydantic.BaseModel):
    """Constant leaf node"""
    success: bool = pydantic.Field(
        True, description="The state to go to when the node is started.")


class MissionRouteNodeV1(pydantic.BaseModel):
    """Specifies waypoints to be executed to by the robot"""
    waypoints: List[common.Pose2D] = pydantic.Field(
        description="Describes a list of pose2D waypoints")

    @property
    def size(self):
        return len(self.waypoints)

    @pydantic.validator("waypoints")
    def _validate_at_least_one_waypoint(cls, value):
        if len(value) < 1:
            raise ValueError("Number of waypoints must be >= 1")
        return value


class MissionNodeV1(pydantic.BaseModel):
    """Specifies a mission node"""
    name: Optional[str] = pydantic.Field(
        None, description="A name for the node")
    parent: str = pydantic.Field(
        "root", description="A parent for the node")
    route: Optional[MissionRouteNodeV1] = pydantic.Field(
        description="A list of poses for the robot to complete.")
    action: Optional[MissionActionNodeV1] = pydantic.Field(
        description="An action for the robot to complete.")
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
            raise ValueError(f"Exactly one of the following must be set {types}, "
                             f"but the following {len(set_types)} are set {set_types}")
        return values

    @property
    def type(self):
        dict_set = self.dict(exclude_unset=True, exclude_none=True)
        for node_type in MissionNodeType:
            if node_type.value in dict_set:
                return node_type


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
            raise ValueError("Number of nodes must be >= 1")

        name_set = set(["root"])
        for i, node in enumerate(value):
            # If no name is provided, assign a default
            if node.name is None:
                node.name = str(i)
            # Make sure all names are unique
            if node.name in name_set:
                raise ValueError(f"MissionNode name {node.name} is repeated. All MissionNode names"
                                 "must be unique.")
            # Make sure the parent appears and it is before the child. This ensures there are no
            # cycles
            if node.parent not in name_set:
                raise ValueError(f"MissionNode \"{node.name}\" has parent \"{node.parent}\" which"
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
    """
    Specifies the supported query parameters allowed for missions
    Currently unimplemented, but possible filters are state,
    start time and end time.

    state: Optional[MissionStateV1]
    start_time: Optional[datetime.datetime]
    end_time: Optional[datetime.datetime]
    """


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
        return MissionSpecV1(robot="NULL", mission_tree=[MissionNodeV1(sequence={})]).dict()

    async def cancel(self):
        if self.status.state.done:
            raise ValueError(
                f"Completed mission {self.name} can't be canceled.")
        self.needs_canceled = True

    async def update(self, update_nodes: Dict[str, MissionRouteNodeV1]):
        if self.status.state.done:
            raise ValueError(
                f"Mission {self.name} is finished with status {self.status.state}.")
        current_node_names = [n.name for n in self.mission_tree]
        for node_name, _ in update_nodes.items():
            if node_name not in current_node_names:
                raise ValueError(
                    f"Node {node_name} does not exist in mission {self.name}")
            elif self.status.state is MissionStateV1.RUNNING and \
                    self.status.node_status[node_name].state.done:
                raise ValueError(
                    f"Mission node {node_name} is finished with status \
                        {self.status.node_status[node_name].state}.")
        # Update when the nodes exist in the mission and the mission is in PENDING or RUNNING state
        self.update_nodes = update_nodes
        return update_nodes
