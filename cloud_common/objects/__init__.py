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
from typing import Dict, List, Type

from cloud_common.objects.mission import MissionObjectV1
from cloud_common.objects.object import ApiObject, ApiObjectMethod, ObjectLifecycleV1
from cloud_common.objects.robot import RobotObjectV1

ALL_OBJECTS: List[Type[ApiObject]] = [RobotObjectV1, MissionObjectV1]
OBJECT_DICT: Dict[str, Type[ApiObject]] = {obj.get_alias(): obj for obj in ALL_OBJECTS}

ApiObjectType = Type[ApiObject]
