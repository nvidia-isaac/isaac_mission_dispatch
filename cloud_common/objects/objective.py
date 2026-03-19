"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2023-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
from __future__ import annotations
from typing import Any, Dict, Union, Optional

import enum
import pydantic.v1 as pydantic

from cloud_common.objects import object

class ObjectiveStateV1(str, enum.Enum):
    """Enum defining the state of the mission."""
    # The first mission has not yet been created
    PENDING = "PENDING"
    # There are still missions waiting to be completed
    RUNNING = "RUNNING"
    # All missions completed
    COMPLETED = "COMPLETED"
    # The objective could not be completed
    FAILED = "FAILED"

    @property
    def done(self):
        return self in (self.COMPLETED, self.FAILED)


class ObjectiveNodeClass(str, enum.Enum):
    """Enum defining the possible objective node class."""
    COMPOSITE = "COMPOSITE"
    BEHAVIOR = "BEHAVIOR"
    DECORATOR = "DECORATOR"


class ObjectiveNodeType(str, enum.Enum):
    """Represents the possible types for all objective nodes."""
    # COMPOSITE types
    SEQUENCE = "SEQUENCE"
    SELECTOR = "SELECTOR"
    PARALLEL = "PARALLEL"

    # BEHAVIOR types
    NAVIGATION = "NAVIGATION"
    CHARGING = "CHARGING"
    UNDOCK = "UNDOCK"
    PICKPLACE = "PICKPLACE"
    MULTI_OBJECT_PICKPLACE = "MULTI_OBJECT_PICKPLACE"
    OBJ_DETECTION = "OBJ_DETECTION"
    APRILTAG_DETECTION = "APRILTAG_DETECTION"
    SLEEP = "SLEEP"

    # DECORATOR types
    RETRY = "RETRY"
    REPEAT = "REPEAT"
    CONDITIONAL = "CONDITIONAL"
    INVERTER = "INVERTER"

    @property
    def is_composite(self):
        return self in (self.SEQUENCE, self.SELECTOR, self.PARALLEL)

    @property
    def is_behavior(self):
        return self in (
            self.NAVIGATION, self.CHARGING, self.UNDOCK, self.PICKPLACE,
            self.OBJ_DETECTION, self.APRILTAG_DETECTION, self.SLEEP,
            self.MULTI_OBJECT_PICKPLACE
        )

    @property
    def is_decorator(self):
        return self in (self.RETRY, self.CONDITIONAL, self.INVERTER, self.REPEAT)


class ObjectiveNode(pydantic.BaseModel):
    """Base class for an Objective Node in a behavior tree"""
    node_class: ObjectiveNodeClass
    node_type: ObjectiveNodeType
    state: ObjectiveStateV1 = ObjectiveStateV1.PENDING


class ObjectiveCompositeNode(ObjectiveNode):
    """Represents an Objective Composite Node in a behavior tree"""
    children: list[Union[ObjectiveCompositeNode, ObjectiveBehaviorNode, ObjectiveDecoratorNode]]

    @pydantic.validator("node_type")
    def node_type_validator(cls, value):
        if not value.is_composite:
            raise ValueError("Invalid node_type for a Composite node.")
        return value

    @pydantic.validator("children")
    def children_validator(cls, value):
        if not isinstance(value, list):
            raise TypeError("Children must be a list.")
        if len(value) == 0:
            raise ValueError("Composite node must have at least one child")
        return value


class ObjectiveBehaviorNode(ObjectiveNode):
    """Represents an Objective Behavior Node in a behavior tree"""
    parameters: dict
    robot: str = ""  # to be assigned by the ObjectiveServer
    mission_id: str = ""
    # NEW: Output specification {"vocabulary_key": "context_variable_name"}
    outputs: Optional[Dict[str, str]] = None

    @pydantic.validator("node_type")
    def node_type_validator(cls, value):
        if not value.is_behavior:
            raise ValueError("Invalid node_type for a Behavior node.")
        return value


class ObjectiveDecoratorNode(ObjectiveNode):
    """Represents an Objective Decorator Node in a behavior tree"""
    parameters: dict
    child: Union[ObjectiveCompositeNode, ObjectiveBehaviorNode, ObjectiveDecoratorNode]

    @pydantic.validator("node_type")
    def node_type_validator(cls, value):
        if not value.is_decorator:
            raise ValueError("Invalid node_type for a Decorator node.")
        return value


ObjectiveCompositeNode.update_forward_refs()
ObjectiveBehaviorNode.update_forward_refs()
ObjectiveDecoratorNode.update_forward_refs()


class ObjectiveStatusV1(pydantic.BaseModel):
    """Represents the status of the robot's object detector."""
    state: ObjectiveStateV1 = ObjectiveStateV1.PENDING
    objective_tree: Optional[Union[ObjectiveCompositeNode,
                                   ObjectiveBehaviorNode, ObjectiveDecoratorNode]] = None
    errors: list[str] = []


class ObjectiveSpecV1(pydantic.BaseModel):
    """Specifies constant properties about the object detector, such as its name."""
    pass
    # objective_tree: Union[ObjectiveCompositeNode, ObjectiveBehaviorNode, ObjectiveDecoratorNode]


class ObjectiveQueryParamsV1(pydantic.BaseModel):
    """Specifies the supported query parameters allowed for obj detectors"""
    pass


class ObjectiveV1(ObjectiveSpecV1, object.ApiObject):
    """Represents an object detector."""
    status: ObjectiveStatusV1

    @classmethod
    def get_alias(cls) -> str:
        return "objective"

    @classmethod
    def get_spec_class(cls) -> Any:
        return ObjectiveSpecV1

    @classmethod
    def get_status_class(cls) -> Any:
        return ObjectiveStatusV1

    @classmethod
    def default_spec(cls) -> Dict:
        return ObjectiveSpecV1().dict()  # type: ignore

    @classmethod
    def get_query_params(cls) -> Any:
        return ObjectiveQueryParamsV1

    @staticmethod
    def get_query_map() -> Dict:
        return {}

    @classmethod
    def supports_spec_update(cls) -> bool:
        return False
