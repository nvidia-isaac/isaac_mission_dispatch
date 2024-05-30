"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2021-2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

from typing import Dict
import logging

class TelemetrySender:
    """ Telemetry Ingestion
    """

    def __init__(self, telemetry_env: str = "DEV") -> None:
        self.logger = logging.getLogger("Isaac Mission Dispatch")
        self.logger.debug("telemetry env: %s", telemetry_env)

    def send_telemetry(self, metrics: Dict,
                       service_name: str = "DISPATCH"):
        """
        Send telemetry data

        Args:
            metrics: metric dictionary to send
            index: the index to send the info to
        """
        self.logger.debug("Send telemetry data.")
