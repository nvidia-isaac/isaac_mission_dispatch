#!/bin/bash
# SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
# Copyright (c) 2024-2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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

set -e

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"
docker build --network host -t isaac-mission-dispatch "${ROOT}/docker"

#Create folder $HOME/.cache/bazel if it does not already exist
if [ ! -d "$HOME/.cache/bazel" ]; then
  mkdir -p "$HOME/.cache/bazel"
fi

#Create folder $HOME/.cache/pip-tools if it does not already exist
if [ ! -d "$HOME/.cache/pip-tools" ]; then
  mkdir -p "$HOME/.cache/pip-tools"
fi

docker run -it --rm \
    --network host \
    --workdir "${ROOT}" \
    -e USER="$(id -u)" \
    -e DISPLAY \
    -v "${ROOT}:${ROOT}" \
    -v /etc/passwd:/etc/passwd:ro \
    -v /etc/group:/etc/group:ro \
    -v "$HOME/.docker:$HOME/.docker:ro" \
    -v "$HOME/.docker/buildx:$HOME/.docker/buildx" \
    -v "/etc/timezone:/etc/timezone:ro" \
    -v "$HOME/.cache/bazel:$HOME/.cache/bazel" \
    -v "$HOME/.cache/pip-tools:$HOME/.cache/pip-tools" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -u $(id -u) \
    --group-add $(getent group docker | cut -d: -f3) \
    isaac-mission-dispatch /bin/bash
