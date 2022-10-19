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
import re
import subprocess
from typing import List, Tuple
import uuid
import time

# Top level bash script to run as init process (PID 1) in each docker container to make sure that
# the docker container exits when the calling python process exits
SH_TEMPLATE = """
EXIT_CODE_FILE=$(mktemp)
cleanup() {
    EXIT_CODE=$(cat $EXIT_CODE_FILE)
    exit $EXIT_CODE
}
trap cleanup INT
( COMMAND ; echo $? > $EXIT_CODE_FILE ; kill -s INT $$ ) &
read _
"""

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
    return process.stdout.decode("utf-8")

def run_docker_target(bazel_target: str, args: List[str] = None,
                      docker_args: List[str] = None,
                      start_timeout: float = 120,
                      delay: int = 0) -> Tuple[subprocess.Popen, str]:
    # Set default arguments
    if args is None:
        args = []

    # Get the path of the bazel image
    regex = r"//(.+):(.+)"
    match = re.match(regex, bazel_target)
    if not match:
        raise ValueError(f"bazel_target \"{bazel_target}\" does not match regex: \"{regex}\"")
    package, target = match.groups()
    bundle_script = f"{package}/{target}"

    # Run the bundle script to add the image to the docker daemon, and get the hash
    bundle_result = subprocess.run([bundle_script], stdout=subprocess.PIPE, check=True)
    image_hash_match = re.search(r"Tagging (.+) as", bundle_result.stdout.decode("utf-8"))
    if not image_hash_match:
        raise ValueError(f"Could not determine image hash for target {bazel_target}")
    image_hash = image_hash_match.groups()[0]

    # Get the entrypoint command
    result = subprocess.run(["docker", "inspect", "-f", "{{.Config.Entrypoint}}", image_hash],
                            stdout=subprocess.PIPE, check=True).stdout.decode('utf-8')
    args = result[1:-2].split(" ") + args
    if delay != 0:
        args = ["sleep", str(delay), ";"] + args

    # Run a the container inside a special bash script that will exit if
    # the calling process dies, so the container will always exit
    name = f'bazel-test-{str(uuid.uuid4())}'
    script = SH_TEMPLATE.replace("COMMAND", " ".join(args))
    docker_cmd = ["docker", "run", "-i", "--rm", "--entrypoint", "sh", "--name", name]
    if docker_args is not None:
        docker_cmd.extend(docker_args)
    docker_cmd.extend([image_hash, "-c", script])
    print(" ".join(docker_cmd), flush=True)
    process = subprocess.Popen(docker_cmd, stdin=subprocess.PIPE)
    try:
        wait_for_container(name, timeout=start_timeout)
        address = get_container_ip(name).strip()
    except:
        process.kill()
        raise
    return process, address
