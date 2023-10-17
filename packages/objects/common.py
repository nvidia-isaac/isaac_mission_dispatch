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
import pydantic
import enum
# Tell pylint to ignore the invalid names. We must use fields that are specified
# by VDA5050.
# pylint: disable=invalid-name


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
