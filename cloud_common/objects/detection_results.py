"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2023-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

from typing import Any, Dict, List, Optional

import pydantic

from cloud_common.objects import object


class Point3D(pydantic.BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0


class Quaternion(pydantic.BaseModel):
    w: float = 0
    x: float = 0
    y: float = 0
    z: float = 0


class Pose3D(pydantic.BaseModel):
    position: Point3D
    orientation: Quaternion


class DetectedObjectCenter2D(pydantic.BaseModel):
    x: float = 0
    y: float = 0
    theta: float = 0


class DetectedObjectBoundingBox2D(pydantic.BaseModel):
    center: Optional[DetectedObjectCenter2D] = None
    size_x: float = 0
    size_y: float = 0


class DetectedObjectBoundingBox3D(pydantic.BaseModel):
    center: Optional[Pose3D] = None
    size_x: float = 0
    size_y: float = 0
    size_z: float = 0


class DetectedObject(pydantic.BaseModel):
    """Represents the detected object from mission client"""
    bbox2d: Optional[DetectedObjectBoundingBox2D] = None
    bbox3d: Optional[DetectedObjectBoundingBox3D] = None
    object_id: int = 0
    class_id: str = ''

    @pydantic.root_validator
    def check_f1_f2(cls, values):
        bbox_2d = values.get('bbox2d')
        bbox_3d = values.get('bbox3d')
        if bbox_2d is None and bbox_3d is None:
            raise ValueError('Either bbox2d or bbox3d must be provided.')
        return values


class DetectionResultsStatusV1(pydantic.BaseModel):
    """Represents the status of the robot's object detector."""
    # A string containing JSON information about all detected
    # objects associated with the paired robot

    # The information will include bounding box information, class,
    # and ID.

    detected_objects: List[DetectedObject] = []


class DetectionResultsSpecV1(pydantic.BaseModel):
    """Specifies constant properties about the object detector, such as its name."""
    pass


class DetectionResultsQueryParamsV1(pydantic.BaseModel):
    """Specifies the supported query parameters allowed for obj detectors"""
    pass


class DetectionResultsObjectV1(DetectionResultsSpecV1, object.ApiObject):
    """Represents an object detector."""
    status: DetectionResultsStatusV1 = DetectionResultsStatusV1()

    @classmethod
    def get_alias(cls) -> str:
        return 'detection_results'

    @classmethod
    def get_spec_class(cls) -> Any:
        return DetectionResultsSpecV1

    @classmethod
    def get_status_class(cls) -> Any:
        return DetectionResultsStatusV1

    @classmethod
    def default_spec(cls) -> Dict:
        return DetectionResultsSpecV1().dict()  # type: ignore

    @classmethod
    def get_query_params(cls) -> Any:
        return DetectionResultsQueryParamsV1

    @staticmethod
    def get_query_map() -> Dict:
        return {

        }

    @classmethod
    def supports_spec_update(cls) -> bool:
        return False
