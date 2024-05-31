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
load("@python_third_party//:requirements.bzl", "requirement")
load("//bzl:python.bzl", "mission_dispatch_py_library")


mission_dispatch_py_library(
    name = "cloud_common_objects",
    srcs = ["cloud_common/objects/common.py",
    "cloud_common/objects/mission.py",
    "cloud_common/objects/object.py",
    "cloud_common/objects/robot.py"],
    data = ["cloud_common/objects/__init__.py"],
    deps = [
        requirement("fastapi"),
        requirement("pydantic"),
        requirement("psycopg")
    ],
    visibility = ["//visibility:public"]
)
