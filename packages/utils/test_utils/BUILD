"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_load")

mission_dispatch_py_library(
    name = "test_utils",
    srcs = [
        "__init__.py",
        "docker.py",
        "network.py",
    ],
    visibility = ["//visibility:public"]
)

oci_image(
    name = "mosquitto-img",
    base = "@mosquitto_base",
    entrypoint = [
        "sh",
        "/mosquitto.sh",
    ],
    tars = [":mosquitto-files-layer"],
)

# Create a tar layer for mosquitto files
genrule(
    name = "mosquitto-files-layer",
    srcs = ["mosquitto.sh"],
    outs = ["mosquitto-files.tar"],
    cmd = "tmpdir=$$(mktemp -d) && cp $(SRCS) $$tmpdir/ && tar -czf $@ -C $$tmpdir . && rm -rf $$tmpdir",
)

oci_load(
    name = "mosquitto-img-bundle",
    image = ":mosquitto-img",
    repo_tags = ["bazel/packages/utils/test_utils/mosquitto:latest"],
    visibility = ["//visibility:public"],
)

oci_image(
    name = "postgres-database-img",
    base = "@postgres_database_base",
    visibility = ["//visibility:public"],
)

oci_load(
    name = "postgres-database-img-bundle",
    image = ":postgres-database-img",
    repo_tags = ["bazel/packages/utils/test_utils/postgres-database:latest"],
    visibility = ["//visibility:public"],
)
