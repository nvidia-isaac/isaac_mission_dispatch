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
load("@python_third_party//:requirements.bzl", "requirement")
load("//bzl:python.bzl", "mission_dispatch_py_binary", "mission_dispatch_py_library")

mission_dispatch_py_library(
    name = "common",
    srcs = [
        "common.py"
    ],
    deps = [
        "//packages/objects",
        requirement("fastapi"),
        requirement("pydantic"),
        requirement("uvicorn")
    ]
)

mission_dispatch_py_binary(
    name = "postgres",
    main = "postgres.py",
    srcs = [
        "postgres.py",
    ],
    deps = [
        ":common",
        "//packages/objects",
        requirement("fastapi"),
        requirement("psycopg"),
    ],
    visibility = ["//visibility:public"],
)

mission_dispatch_py_library(
    name = "client",
    srcs = ["client.py"],
    deps = [
        "//packages/objects",
        requirement("pydantic"),
        requirement("requests"),
    ],
    visibility = ["//visibility:public"]
)
