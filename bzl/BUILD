# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2021-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

load("@python_versions//3.10:defs.bzl", compile_pip_requirements = "compile_pip_requirements")

package(default_visibility = ["//visibility:public"])

compile_pip_requirements(
    name = "python_third_party",
    src = "requirements.txt",
    requirements_txt = "requirements_lock.txt",
)

compile_pip_requirements(
    name = "python_third_party_linting",
    src = "requirements_linting.txt",
    requirements_txt = "requirements_linting_lock.txt",
)

exports_files([
    "pylintrc",
    "pytype.py",
    "pylint.py",
    "requirements.txt",
    "requirements_lock.txt",
    "requirements_linting.txt",
    "requirements_linting_lock.txt",
])
