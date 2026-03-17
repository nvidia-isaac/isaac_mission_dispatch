"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2025-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

from typing import Any, Dict, List

import pydantic.v1 as pydantic

from cloud_common.objects import object
from cloud_common.objects.common import Pose3D


class AprilTagCenter2D(pydantic.BaseModel):
    x: float
    y: float


class DetectedAprilTag(pydantic.BaseModel):
    """Represents a detected AprilTag from the robot's camera"""
    tag_id: int
    family: str
    center: AprilTagCenter2D
    pose: Pose3D
    frame_id: str
    timestamp: float


class AprilTagResultsStatusV1(pydantic.BaseModel):
    """Represents the status of the robot's AprilTag detector."""
    # A list containing all detected AprilTags associated with the paired robot
    # The information includes tag ID, family, pixel coordinates, 3D pose, and frame ID
    detected_apriltags: List[DetectedAprilTag] = pydantic.Field(default_factory=list)


class AprilTagResultsSpecV1(pydantic.BaseModel):
    """Specifies constant properties about the AprilTag detector, such as its name."""
    pass


class AprilTagResultsQueryParamsV1(pydantic.BaseModel):
    """Specifies the supported query parameters allowed for AprilTag detectors"""
    pass


class AprilTagResultsObjectV1(AprilTagResultsSpecV1, object.ApiObject):
    """Represents an AprilTag detector."""
    status: AprilTagResultsStatusV1 = pydantic.Field(default_factory=AprilTagResultsStatusV1)

    @classmethod
    def get_alias(cls) -> str:
        return 'apriltag_results'

    @classmethod
    def get_spec_class(cls) -> Any:
        return AprilTagResultsSpecV1

    @classmethod
    def get_status_class(cls) -> Any:
        return AprilTagResultsStatusV1

    @classmethod
    def default_spec(cls) -> Dict:
        return AprilTagResultsSpecV1().dict()  # type: ignore

    @classmethod
    def get_query_params(cls) -> Any:
        return AprilTagResultsQueryParamsV1

    @staticmethod
    def get_query_map() -> Dict:
        return {}

    @classmethod
    def supports_spec_update(cls) -> bool:
        return False
