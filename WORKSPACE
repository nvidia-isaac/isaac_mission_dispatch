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
workspace(name="com_nvidia_isaac_mission_dispatch")

load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

# Include rules needed for pip
load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

http_archive(
    name="rules_python",
    sha256="778aaeab3e6cfd56d681c89f5c10d7ad6bf8d2f1a72de9de55b23081b2d31618",
    strip_prefix="rules_python-0.34.0",
    url="https://github.com/bazelbuild/rules_python/releases/download/0.34.0/rules_python-0.34.0.tar.gz",
)

load("@rules_python//python:repositories.bzl", "py_repositories")

py_repositories()

# Include rules
http_archive(
    name="io_bazel_rules_docker",
    sha256="b1e80761a8a8243d03ebca8845e9cc1ba6c82ce7c5179ce2b295cd36f7e394bf",
    urls=["https://github.com/bazelbuild/rules_docker/releases/download/v0.25.0/rules_docker-v0.25.0.tar.gz"],
)
load("@io_bazel_rules_docker//repositories:repositories.bzl",
     container_repositories="repositories")
container_repositories()


# Setup workspace for mission dispatch
load("//:deps.bzl", "mission_dispatch_workspace")
load("@rules_python//python:pip.bzl", "pip_parse")
# Install python dependencies from pip
pip_parse(
    name="python_third_party",
    requirements_lock="@com_nvidia_isaac_mission_dispatch//bzl:requirements.txt"
)

load("@python_third_party//:requirements.bzl", "install_deps")
install_deps()

# Install linting dependencies from pip
pip_parse(
    name="python_third_party_linting",
    requirements_lock="@com_nvidia_isaac_mission_dispatch//bzl:requirements_linting.txt"
)

load("@python_third_party_linting//:requirements.bzl", "install_deps")
install_deps()

mission_dispatch_workspace()
