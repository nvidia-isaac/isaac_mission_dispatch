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
load("//bzl:python.bzl", "mission_dispatch_py_library")
load("@io_bazel_rules_docker//container:container.bzl", "container_image", "container_bundle")

mission_dispatch_py_library(
    name = "test_utils",
    srcs = [
        "__init__.py",
        "docker.py",
        "network.py",
    ],
    visibility = ["//visibility:public"]
)

container_image(
    name = "mosquitto-img",
    base = "@mosquitto_base//image",
    files = [
        "mosquitto.sh"
    ],
    entrypoint = ["sh", "mosquitto.sh"]
)

container_bundle(
    name = "mosquitto-img-bundle",
    images = {
        "bazel-image": ":mosquitto-img"
    },
    visibility = ["//visibility:public"]
)

container_bundle(
    name = "postgres-database-img-bundle",
    images = {
        "bazel-image": "@postgres_database_base//image"
    },
    visibility = ["//visibility:public"]
)
