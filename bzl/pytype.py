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
import os
import subprocess
import sys


def shadowed_module(path: str) -> bool:
    """ Whether a path indicates a module that shadows a dist-package and should be excluded from
    mypy """
    shadowed_modules = [
        "pypi__typing_extensions"
    ]
    return any(module in path for module in shadowed_modules)


def main():
    # Determine the module include paths that should be used by mypy
    paths = os.environ["PYTHONPATH"]
    fixed_paths = ":".join(path for path in paths.split(":") if not shadowed_module(path))
    env = {
        "PYTHONPATH": paths,
        "MYPYPATH": fixed_paths
    }

    # Run mypy in a subprocess
    result = subprocess.run([sys.executable, "-m", "mypy",
                             "--explicit-package-bases", "--namespace-packages",
                             "--follow-imports", "silent", "--check-untyped-defs"] + sys.argv[1:],
                            env=env)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
