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
import contextlib
import socket
import time

# How often to poll to see if a port is open
PORT_CHECK_PERIOD = 0.1

def check_port_open(port: int, host: str = "localhost") -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as test_socket:
        return test_socket.connect_ex((host, port)) == 0


def wait_for_port(port: int, timeout: float = float("inf"), host: str = "localhost"):
    end_time = time.time() + timeout
    while time.time() < end_time:
        if check_port_open(host=host, port=port):
            return
        time.sleep(PORT_CHECK_PERIOD)
    raise ValueError(f"Port {host}:{port} did not open in time")
