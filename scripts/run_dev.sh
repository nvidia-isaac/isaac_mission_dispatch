#!/bin/bash
# Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

set -e

ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/.. >/dev/null 2>&1 && pwd )"
docker build --network host -t isaac-mission-dispatch "${ROOT}/docker"

#Create folder $HOME/.cache/bazel if it does not already exist
if [ ! -d "$HOME/.cache/bazel" ]; then
  mkdir -p "$HOME/.cache/bazel"
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
    -v /var/run/docker.sock:/var/run/docker.sock \
    -u $(id -u) \
    --group-add $(getent group docker | cut -d: -f3) \
    isaac-mission-dispatch /bin/bash
