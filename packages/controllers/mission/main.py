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
import argparse
import logging
import sys

from packages.controllers.mission import server as mission_server

LOGGING_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mqtt_host", default="localhost",
                        help="The hostname of the mqtt server to connect to")
    parser.add_argument("--mqtt_port", default=1883, type=int,
                        help="The port of the mqtt server to connect to")
    parser.add_argument("--mqtt_transport", default="tcp", choices=("tcp", "websockets"),
                        help="Set transport mechanism as WebSockets or raw TCP")
    parser.add_argument("--mqtt_ws_path", default=None,
                        help="The path for the websocket if mqtt_transport is websockets")
    parser.add_argument("--mqtt_prefix", default="uagv/v1",
                        help="The prefix to add to all VDA5050 mqtt topics")
    parser.add_argument("--database_url", default="http://localhost:5001",
                        help="The url where the database REST API is hosted")
    parser.add_argument("--log_level", default="INFO", choices=LOGGING_LEVELS,
                        help="The minimum level of log messages to print")
    args = parser.parse_args()
    logger = logging.getLogger("Isaac Mission Dispatch")
    logger.setLevel(args.log_level)
    logger.addHandler(logging.StreamHandler(sys.stderr))
    del args.log_level
    server = mission_server.RobotServer(**vars(args))
    server.run()
