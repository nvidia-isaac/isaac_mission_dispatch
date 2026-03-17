"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

import pydantic.v1 as pydantic
from fastapi import Query
from pydantic.v1 import Field

from cloud_common.objects import common, object


class VDA5050AgvClass(str, enum.Enum):
    """Simplified description of the AGV class"""
    FORKLIFT = "FORKLIFT"  # Forklift
    CONVEYOR = "CONVEYOR"  # AGV with conveyors on it
    TUGGER = "TUGGER"      # Tugger
    CARRIER = "CARRIER"    # Load carrier with or without lifting unit
    MANIPULATOR = "MANIPULATOR"  # Stationary Manipulator
    HUMANOID = "HUMANOID"  # Mobile Manipulator


class RobotStateV1(enum.Enum):
    """Robot state
    """
    IDLE = "IDLE"
    ON_TASK = "ON_TASK"
    CHARGING = "CHARGING"
    MAP_DEPLOYMENT = "MAP_DEPLOYMENT"
    TELEOP = "TELEOP"

    @property
    def running(self):
        return self in (RobotStateV1.ON_TASK, RobotStateV1.MAP_DEPLOYMENT, RobotStateV1.CHARGING)

    @property
    def can_switch_teleop(self):
        return self in (RobotStateV1.IDLE, RobotStateV1.ON_TASK,
                        RobotStateV1.MAP_DEPLOYMENT, RobotStateV1.TELEOP)

    @property
    def can_deploy_map(self):
        return self in (RobotStateV1.IDLE, RobotStateV1.CHARGING)


class RobotTeleopActionV1(enum.Enum):
    START = "START"
    STOP = "STOP"


class RobotSoftwareVersionV1(pydantic.BaseModel):
    os: str = ""
    app: str = ""


class RobotHardwareVersionV1(pydantic.BaseModel):
    manufacturer: str = ""
    serial_number: str = ""


class RobotTypeIdentifierV1(pydantic.BaseModel):
    """Represents the type and capabilities of a robot.

    Attributes:
        agv_class: The VDA5050 classification of the robot (e.g. CARRIER, FORKLIFT).
                  Defaults to CARRIER if not specified.
        speed_max: Maximum speed of the robot in meters per second.
    """
    agv_class: str = VDA5050AgvClass.CARRIER.value
    speed_max: float = -1

    @pydantic.validator("agv_class", pre=True, always=True)
    def _validate_agv_class(cls, value):  # pylint: disable=no-self-argument
        """Validate that the provided AGV class string is a valid VDA5050AgvClass value.

        This validator ensures that the agv_class field contains a valid string value
        from the VDA5050AgvClass enum.
        """
        # Default / missing value → fall back to historical default (CARRIER)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return VDA5050AgvClass.CARRIER.value

        # If it's already a VDA5050AgvClass enum, get its value
        if isinstance(value, VDA5050AgvClass):
            return value.value

        # Otherwise, validate the string value
        if isinstance(value, str):
            cleaned = value.strip().upper()
            try:
                # Validate by trying to create the enum
                VDA5050AgvClass(cleaned)
                return cleaned
            except ValueError as exc:
                raise ValueError(
                    f"Invalid VDA5050AgvClass '{value}'. "
                    f"Allowed values: {[e.value for e in VDA5050AgvClass]}"
                ) from exc

        # Fallback – unsupported type
        raise ValueError(
            f"Unsupported type for agv_class: {type(value).__name__}. Expected VDA5050AgvClass."
        )


class RobotBatterySpecV1(pydantic.BaseModel):
    """Represents the specs of the robot's battery."""
    critical_level: float = 10.0
    recommended_minimum: Optional[float] = None
    recommended_maximum: Optional[float] = None


class RobotStatusV1(pydantic.BaseModel):
    """Represents the status of the robot."""
    pose: common.Pose2D = common.Pose2D()
    position_initialized: bool = False
    software_version: RobotSoftwareVersionV1 = RobotSoftwareVersionV1()
    hardware_version: RobotHardwareVersionV1 = RobotHardwareVersionV1()
    factsheet: RobotTypeIdentifierV1 = RobotTypeIdentifierV1()
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
    switch_teleop: bool = pydantic.Field(
        False, description="Toggle the mode of the robot to TELEOP."
    )


class RobotQueryParamsV1(pydantic.BaseModel):
    """Specifies the supported query parameters allowed for robots"""
    min_battery: Optional[float]
    max_battery: Optional[float]
    state: Optional[RobotStateV1]
    online: Optional[bool]
    position_initialized: Optional[bool]
    names: Optional[List[str]] = Field(Query(None))
    robot_type: Optional[VDA5050AgvClass]


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
        return RobotSpecV1().dict()  # type: ignore

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
            "online": "status->>'online' = '{}'",
            "position_initialized": "status->>'position_initialized' = '{}'",
            "robot_type": "(status->'factsheet'->>'agv_class')::text = '{}'"
        }

    @classmethod
    def get_methods(cls) -> List[object.ApiObjectMethod]:
        return [
            object.ApiObjectMethod(
                name="teleop", description="This endpoint is to place the robot into teleop or \
                    to take the robot out of teleop.",
                function=cls.teleop,
                params=RobotTeleopActionV1)
        ]

    async def teleop(self, teleop: RobotTeleopActionV1):
        if not self.status.state.can_switch_teleop:
            raise common.ICSUsageError(
                f"Robot {self.name} is in {self.status.state} and request cannot be satisfied.")
        self.switch_teleop = (teleop == RobotTeleopActionV1.START)
        return teleop.value + " teleop action received."
