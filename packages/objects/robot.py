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
import datetime
import enum
from typing import Any, Dict, List, Optional

import pydantic

from packages.objects import common, object

class RobotStateV1(str, enum.Enum):
    IDLE = "IDLE"
    ON_TASK = "ON_TASK"

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
