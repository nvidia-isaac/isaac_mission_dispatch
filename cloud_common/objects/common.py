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
import enum

import pydantic

# Tell pylint to ignore the invalid names. We must use fields that are specified
# by VDA5050.
# pylint: disable=invalid-name


class ICSError(Exception):
    """
    Base class for exceptions in this module.
    If unexpected Error occurs user will be shown this error.
    """
    error_code: str = "ICS_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __repr__(self):
        return f"{self.__class__.__name__}: {self.message}"

    def __str__(self):
        return self.message


class ICSUsageError(ICSError):
    """ Exception raised for errors to notify users with appropriate message. """
    error_code: str = "USAGE"


class ICSServerError(ICSError):
    """ Exception raised for errors in the server. """
    error_code: str = "SERVER"


class TaskType(enum.Enum):
    MISSION = "MISSION"
    MAP_UPDATE = "MAP_UPDATE"


class Pose2D(pydantic.BaseModel):
    """Specifies a pose to be traveled to by the robot"""
    x: float = pydantic.Field(
        description="The x coordinate of the pose in meters", default=0.0)
    y: float = pydantic.Field(
        description="The y coordinate of the pose in meters", default=0.0)
    theta: float = pydantic.Field(
        description="The rotation of the pose in radians", default=0.0)
    map_id: str = pydantic.Field(
        description="The ID of the map this pose is associated with", default="")
    allowedDeviationXY: float = pydantic.Field(
        description="Allowed coordinate deviation radius",
        default=0.0)
    allowedDeviationTheta: float = pydantic.Field(
        description="Allowed theta deviation radians",
        default=0.0)


def handle_response(response):
    if response.status_code >= 400 and response.status_code < 500:
        raise ICSUsageError(response.text)
    if response.status_code >= 500:
        raise ICSServerError(response.text)
