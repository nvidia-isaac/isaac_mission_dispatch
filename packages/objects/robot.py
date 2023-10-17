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
from fastapi import Query
import pydantic
from pydantic import Field
from packages.objects import common, object


class RobotStateV1(enum.Enum):
    IDLE = "IDLE"
    ON_TASK = "ON_TASK"
    # TODO(danyu): Update robot state to charging once charging actions are ready
    CHARGING = "CHARGING"
    MAP_DEPLOYMENT = "MAP_DEPLOYMENT"

    @property
    def running(self):
        return self in (RobotStateV1.ON_TASK, RobotStateV1.MAP_DEPLOYMENT)


class RobotSoftwareVersionV1(pydantic.BaseModel):
    os: str = ""
    app: str = ""


class RobotHardwareVersionV1(pydantic.BaseModel):
    manufacturer: str = ""
    serial_number: str = ""


class RobotBatterySpecV1(pydantic.BaseModel):
    """Represents the specs of the robot's battery."""
    critical_level: float = 0.1
    recommended_minimum: Optional[float] = None
    recommended_maximum: Optional[float] = None


class RobotStatusV1(pydantic.BaseModel):
    """Represents the status of the robot."""
    pose: common.Pose2D = common.Pose2D()
    software_version: RobotSoftwareVersionV1 = RobotSoftwareVersionV1()
    hardware_version: RobotHardwareVersionV1 = RobotHardwareVersionV1()
    online: bool = False
    battery_level: float = 0.0
    state: RobotStateV1 = RobotStateV1.IDLE
    info_messages: Optional[Dict] = pydantic.Field(
        None, description="Data collected from the mission client.")
    errors: Dict = pydantic.Field(
        {}, description="Key value pairs to describe if something is wrong with the robot.")


class RobotSpecV1(pydantic.BaseModel):
    """Specifies constant properties about the robot, such as its name."""
    labels: List[str] = pydantic.Field(
        [], description="A list of labels to assign to the robot, used to identify certain groups \
                        of robots.")
    battery: RobotBatterySpecV1 = RobotBatterySpecV1()
    heartbeat_timeout: datetime.timedelta = pydantic.Field(
        datetime.timedelta(seconds=30),
        description="The window of time after the dispatch gets a message from a robot for a \
                     robot to be considered online")


class RobotQueryParamsV1(pydantic.BaseModel):
    """Specifies the supported query parameters allowed for robots"""
    min_battery: Optional[float]
    max_battery: Optional[float]
    state: Optional[RobotStateV1]
    online: Optional[bool]
    names: Optional[List[str]] = Field(Query(None))


class RobotObjectV1(RobotSpecV1, object.ApiObject):
    """Represents a robot."""
    status: RobotStatusV1

    @classmethod
    def get_alias(cls) -> str:
        return "robot"

    @classmethod
    def get_spec_class(cls) -> Any:
        return RobotSpecV1

    @classmethod
    def get_status_class(cls) -> Any:
        return RobotStatusV1

    @classmethod
    def default_spec(cls) -> Dict:
        return RobotSpecV1().dict()

    @classmethod
    def get_query_params(cls) -> Any:
        return RobotQueryParamsV1

    @staticmethod
    def get_query_map() -> Dict:
        return {
            "min_battery": "(status->'battery_level')::float >= {}",
            "max_battery": "(status->'battery_level')::float <= {}",
            "names": "name in {}",
            "state": "status->>'state' = '{}'",
            "online": "status->>'online' = '{}'"
        }
