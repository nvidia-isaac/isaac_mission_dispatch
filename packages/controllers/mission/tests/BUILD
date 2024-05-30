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
load("//bzl:python.bzl", "mission_dispatch_py_binary")
load("//bzl:python.bzl", "mission_dispatch_py_library")
load("@python_third_party//:requirements.bzl", "requirement")

mission_dispatch_py_binary(
    name = "client",
    srcs = ["client.py"],
    deps = [
        "//packages/controllers/mission/vda5050_types",
        requirement("paho-mqtt"),
        requirement("pydantic")
    ],
    visibility = ["//visibility:public"]
)

py_library(
    name = "test_context",
    srcs = [
        "test_context.py"
    ],
    deps = [
        "//packages/database:client",
        "//packages/utils/test_utils",
        ":client",
        requirement("requests")
    ],
    data = [
        "//packages/controllers/mission:mission-img-bundle",
        "//packages/controllers/mission/tests:client-img-bundle",
        "//packages/database:postgres-img-bundle",
        "//packages/utils/test_utils:postgres-database-img-bundle",
        "//packages/utils/test_utils:mosquitto-img-bundle"
    ],
)

mission_dispatch_py_library(
    name = "mission_examples",
    srcs = [
        "mission_examples.py"
    ],
)

py_test(
    name = "cancel_mission",
    srcs = [
        "cancel_mission.py"
        ],
    deps = [
        ":test_context",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "delete_robot",
    srcs = [
        "delete_robot.py"
    ],
    deps = [
        ":test_context",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "fail_robot",
    srcs = [
        "fail_robot.py"
    ],
    deps = [
        ":test_context",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "mission",
    srcs = [
        "mission.py"
    ],
    deps = [
        ":test_context",
        ":mission_examples",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "robot",
    srcs = [
        "robot.py"
    ],
    deps = [
        ":test_context"
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "start_order",
    srcs = [
        "start_order.py"
    ],
    deps = [
        ":test_context",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "mission_tree",
    srcs = [
        "mission_tree.py"
    ],
    deps = [
        ":test_context",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "server",
    srcs = [
        "server.py"
    ],
    deps = [
        ":test_context",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)

py_test(
    name = "update_mission",
    srcs = [
        "update_mission.py"
    ],
    deps = [
        ":test_context",
    ],
    tags = [
        "exclusive"
    ],
    size = "large"
)
