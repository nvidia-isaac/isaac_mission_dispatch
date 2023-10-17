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
import abc
import base64
import enum
from typing import Any, Callable, List, NamedTuple, Optional, Type, Dict
import uuid

import pydantic

# The number of characters to include in the short object ID
SHORT_ID_LENGTH = 8

class ObjectLifecycleV1(str, enum.Enum):
    ALIVE = "ALIVE"
    PENDING_DELETE = "PENDING_DELETE"
    DELETED = "DELETED"


class ApiObjectMethod(NamedTuple):
    name: str
    description: str
    function: Callable
    params: Optional[Type] = None
    returns: Optional[Type] = None


class ApiObject(pydantic.BaseModel, metaclass=abc.ABCMeta):
    """Represents an api object with a specification and a state"""

    # Every API object has a unique name
    name: str
    status: Any = None
    lifecycle: ObjectLifecycleV1 = ObjectLifecycleV1.ALIVE

    def __init__(self, *args, **kwargs):
        if kwargs.get("name") is None:
            kwargs["name"] = self.get_uuid()
        super().__init__(*args, **kwargs)

    def update(self, properties: Any):
        for key, value in properties:
            setattr(self, key, value)

    @property
    def spec(self) -> Any:
        return self.get_spec_class()(**self.dict())

    @classmethod
    @abc.abstractmethod
    def get_alias(cls) -> str:
        pass

    @classmethod
    @abc.abstractmethod
    def get_spec_class(cls) -> Any:
        pass

    @classmethod
    @abc.abstractmethod
    def get_status_class(cls) -> Any:
        pass

    @classmethod
    @abc.abstractmethod
    def get_query_params(cls) -> Any:
        pass

    @staticmethod
    def get_query_map() -> Dict:
        return {}

    @classmethod
    def get_methods(cls) -> List[ApiObjectMethod]:
        return []

    @classmethod
    def supports_spec_update(cls) -> bool:
        return True

    @classmethod
    def table_name(cls):
        return cls.__name__.lower()

    @classmethod
    def get_uuid(cls) -> str:
        return base64.b32encode(uuid.uuid4().bytes).lower().decode("utf-8").replace("=", "")

    @classmethod
    def default_spec(cls):
        pass
