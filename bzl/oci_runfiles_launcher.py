# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

"""Run a py_binary main.py with the container base Python and Bazel runfiles layout.

rules_python's default bootstrap execs the hermetic interpreter under .runfiles via
a shell. Distroless base images have no shell (and we omit the hermetic interpreter),
so the base /usr/local/bin/python3 must still see the same import paths the bootstrap
would have set up: the workspace root (_main) and every pip .../site-packages tree
under RUNFILES_DIR.
"""

from __future__ import annotations

import os
import runpy
import sys


def _prepend_runfiles_import_path(runfiles: str) -> None:
    sites: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(runfiles):
        if os.path.basename(dirpath) == "site-packages":
            sites.append(dirpath)
            dirnames.clear()
    prefix = [os.path.join(runfiles, "_main")] + sites
    sys.path[:0] = prefix


def main() -> None:
    runfiles = os.environ.get("RUNFILES_DIR")
    if not runfiles or not os.path.isdir(runfiles):
        sys.stderr.write(
            "oci_runfiles_launcher: RUNFILES_DIR must be set to the *.runfiles directory\n",
        )
        sys.exit(1)

    if len(sys.argv) < 2:
        sys.stderr.write(
            "usage: oci_runfiles_launcher.py <path-to-main.py> [args...]\n",
        )
        sys.exit(2)

    main_py = sys.argv[1]
    sys.argv = sys.argv[1:]
    _prepend_runfiles_import_path(runfiles)
    runpy.run_path(main_py, run_name="__main__")


if __name__ == "__main__":
    main()
