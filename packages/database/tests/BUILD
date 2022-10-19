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
load("//bzl:python.bzl", "mission_dispatch_py_library")

mission_dispatch_py_library(
    name="test_base",
    srcs=[
        "test_base.py"
    ],
    deps=[
        "//packages/utils/test_utils",
        "//packages/objects",
    ],
    visibility = ["//visibility:public"]
)

py_test(
    name="postgres",
    srcs=[
        "postgres.py"
    ],
    deps=[
        "//packages/database:client",
        "//packages/utils/test_utils",
        "//packages/database/tests:test_base",
    ],
    data = [
        "//packages/database:postgres-img-bundle",
        "//packages/utils/test_utils:postgres-database-img-bundle"
    ]
)
