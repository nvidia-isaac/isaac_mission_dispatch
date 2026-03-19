"""
Python build macros for Mission Dispatch project.

Provides custom wrappers around aspect_rules_py that add:
- Type checking with mypy
- Linting with pylint  
- OCI image generation for deployable binaries

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
load("@python_third_party_linting//:requirements.bzl", "requirement")
load("@aspect_rules_py//py:defs.bzl", "py_binary", "py_image_layer", "py_library")
load("@rules_oci//oci:defs.bzl", "oci_image", "oci_load")

def py_type_test(name, srcs, deps):
    """
    Create a mypy type checking test for Python sources.
    
    Args:
        name: Name of the test target
        srcs: List of Python source files to type check
        deps: Dependencies required for type checking
    """
    native.py_test(
        name = name,
        main = "@com_nvidia_isaac_mission_dispatch//bzl:pytype.py",
        srcs = ["@com_nvidia_isaac_mission_dispatch//bzl:pytype.py"],
        data = srcs,
        deps = deps + [requirement("mypy")],
        args = ["$(location {})".format(src) for src in srcs],
        tags = ["lint"],
    )

def py_lint_test(name, srcs):
    """
    Create a pylint code quality test for Python sources.
    
    Args:
        name: Name of the test target
        srcs: List of Python source files to lint
    """
    native.py_test(
        name = name,
        main = "@com_nvidia_isaac_mission_dispatch//bzl:pylint.py",
        srcs = ["@com_nvidia_isaac_mission_dispatch//bzl:pylint.py"],
        data = srcs + ["@com_nvidia_isaac_mission_dispatch//bzl:pylintrc"],
        deps = [requirement("pylint")],
        args = ["--rcfile=$(location @com_nvidia_isaac_mission_dispatch//bzl:pylintrc)"] +
               ["$(location {})".format(src) for src in srcs],
        tags = ["lint"],
    )

def mission_dispatch_py_library(**kwargs):
    """
    Create a Python library target.
    
    Wraps aspect_rules_py py_library without lint/type tests.
    Add py_lint_test/py_type_test targets separately when needed.
    
    Args:
        **kwargs: Arguments passed through to py_library
    """
    py_library(**kwargs)

def mission_dispatch_py_binary(**kwargs):
    """
    Create a Python binary target with linting, type checking, and OCI image.
    
    Generates the following targets:
    - {name}: The py_binary executable
    - {name}-type-test: mypy type checking test
    - {name}-lint-test: pylint code quality test
    - {name}-img: OCI image with the binary as entrypoint
    - {name}-img-bundle: Loadable OCI image tarball
    
    Args:
        **kwargs: Arguments for py_binary (name, srcs, deps, etc.)
    """
    name = kwargs["name"]
    
    # Create the binary
    py_binary(**kwargs)
    
    # Create lint and type tests
    py_type_test(
        name = name + "-type-test",
        srcs = kwargs.get("srcs", []),
        deps = kwargs.get("deps", []),
    )
    py_lint_test(
        name = name + "-lint-test",
        srcs = kwargs.get("srcs", []),
    )

    # Create image layer from binary
    py_image_layer(
        name = name + "-image-layer",
        binary = name,
    )

    # Determine package path for entrypoint
    # py_image_layer preserves workspace structure:
    # Binary at //packages/database:postgres -> /packages/database/postgres
    package_path = native.package_name()
    if package_path:
        entrypoint = "/" + package_path + "/" + name
        repo_tag = package_path.replace("/", "-") + "-" + name + ":latest"
    else:
        entrypoint = "/" + name
        repo_tag = name + ":latest"

    # Create OCI image
    oci_image(
        name = name + "-img",
        base = "@python",  # Python 3.10 base image from MODULE.bazel
        entrypoint = [entrypoint],
        tars = [name + "-image-layer"],
    )

    # Create loadable image bundle for local testing
    # Tag bundles with package + target for easy local identification
    oci_load(
        name = name + "-img-bundle",
        image = name + "-img",
        repo_tags = [repo_tag],
        visibility = ["//visibility:public"],
    )
