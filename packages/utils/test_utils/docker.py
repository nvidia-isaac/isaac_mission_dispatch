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
import json
import os
import re
import socket
import subprocess
import time
import uuid
from typing import List, Tuple, Union
from urllib.parse import urlparse

# How often to poll to see if a container is running
CONTAINER_CHECK_PERIOD = 0.1


def check_container_running(name: str) -> bool:
    result = subprocess.run(["docker", "container", "inspect", name], # pylint: disable=subprocess-run-check
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    return result.returncode == 0

def wait_for_container(name: str, timeout: float = float("inf")):
    end_time = time.time() + timeout
    while time.time() < end_time:
        if check_container_running(name):
            return
        time.sleep(CONTAINER_CHECK_PERIOD)
    raise ValueError("Container did not start in time")

def get_container_ip(name: str) -> str:
    process = subprocess.run(["docker", "inspect", "-f",
                              "{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name],
                             stdout=subprocess.PIPE, check=True)
    ip_address = process.stdout.decode("utf-8").strip()
    if not ip_address or ip_address == "invalid IP":  # Host network mode can sometimes return "invalid IP"
        docker_host = os.environ.get("DOCKER_HOST", "")
        if docker_host:
            if "://" not in docker_host:
                docker_host = f"tcp://{docker_host}"
            parsed = urlparse(docker_host)
            hostname = parsed.hostname
            if hostname:
                try:
                    return socket.gethostbyname(hostname)
                except socket.gaierror:
                    # If hostname resolution fails, fall back to 127.0.0.1
                    return "127.0.0.1"
        return "127.0.0.1"
    return ip_address

def run_docker_target(bazel_target: str, args: Union[List[str], None] = None,
                      docker_args: Union[List[str], None] = None,
                      start_timeout: float = 120,
                      delay: int = 0,
                      name: Union[str, None] = None) -> Tuple[subprocess.Popen, str]:
    """Load a bazel image bundle and run it as a container.

    The container runs with the image's own entrypoint (no shell wrapper), so it
    works with shell-less base images such as nvidia/distroless/python. The caller is
    responsible for stopping the container (by name) when done; see TestContext.close.
    """
    # Set default arguments
    if args is None:
        args = []

    # Get the path of the bazel image
    regex = r"//(.+):(.+)"
    match = re.match(regex, bazel_target)
    if not match:
        raise ValueError(f"bazel_target \"{bazel_target}\" does not match regex: \"{regex}\"")
    package, target = match.groups()
    bundle_script = os.path.join(package, f"{target}.sh")

    # Run the bundle script to add the image to the docker daemon, and get the hash
    subprocess.run([bundle_script], stdout=subprocess.DEVNULL, check=True)
    bundle_manifest = os.path.join(package, target, "manifest.json")
    with open(bundle_manifest, "r") as f:
        manifest = json.load(f)
    if not manifest or "Config" not in manifest[0]:
        raise ValueError(f"Invalid manifest contents in {bundle_manifest}")
    # Prefer the repo tag assigned by docker load; config digests are not
    # reliably inspectable as image IDs on modern Docker.
    repo_tags = manifest[0].get("RepoTags") or []
    if repo_tags:
        image_ref = repo_tags[0]
    else:
        config_name = manifest[0]["Config"].split("/")[-1]
        if config_name.startswith("sha256:"):
            config_name = config_name[len("sha256:"):]
        if config_name.endswith(".json"):
            config_name = config_name[:-5]
        image_ref = f"sha256:{config_name}"

    # Optionally delay the container start (used to test start ordering). Done here in
    # Python rather than via a shell "sleep" so no shell is required in the image.
    if delay != 0:
        time.sleep(delay)

    # Run the container with the image's own entrypoint; args are appended as CMD.
    if name is None:
        name = f"bazel-test-{str(uuid.uuid4())}"
    docker_cmd = ["docker", "run", "--rm", "--name", name]
    if docker_args is not None:
        docker_cmd.extend(docker_args)
    docker_cmd.append(image_ref)
    docker_cmd.extend(args)
    print(" ".join(docker_cmd), flush=True)
    process = subprocess.Popen(docker_cmd) # pylint: disable=consider-using-with
    try:
        wait_for_container(name, timeout=start_timeout)
        address = get_container_ip(name).strip()
    except Exception:
        process.kill()
        subprocess.run(["docker", "rm", "-f", name], # pylint: disable=subprocess-run-check
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raise
    return process, address
