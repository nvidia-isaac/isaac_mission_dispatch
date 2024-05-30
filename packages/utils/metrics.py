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
import enum
from typing import Union


class Timeframe(enum.Enum):
    RUNTIME = "RUNTIME"
    DAILY = "DAILY"
    MISSION = "MISSION"
    ROBOT = "ROBOT"


class Telemetry:
    """ Collect telemetry data
    """

    def __init__(self):
        """
        Initialize the Telemetry object.
        """
        self.data = {}

    def add_kpi(self, name: str, value: Union[float, dict, str], frequency: Timeframe):
        """
        Add a scalar KPI to telemetry data.

        Args:
            name (str): The name of the KPI.
            value (Union[float, dict, str]): The value of the KPI.
            frequency (Timeframe): The frequency at which the KPI should be recorded.
        """
        if frequency.value not in self.data:
            self.data[frequency.value] = {}

        self.data[frequency.value][name] = value

    def aggregate_scalar_kpi(self, name: str, value: float, frequency: Timeframe):
        """
        Calculate statistics or aggregate values for a specific KPI.

        Args:
            name (str): The name of the KPI.
            value (str): The string value of the KPI.
            frequency (Timeframe): The frequency at which the KPI should be recorded.
        """
        if frequency.value not in self.data:
            self.data[frequency.value] = {}
        self.data[frequency.value][name] += value

    def get_kpis_by_frequency(self, frequency: Timeframe):
        """
        Retrieve KPIs for a specific frequency.

        Args:
            frequency (Timeframe): The frequency for which KPIs should be retrieved.

        Returns:
            dict: A dictionary containing the KPIs for the specified frequency.
        """
        result = [{k: v} for k, v in self.data.items() if k == frequency.value]
        return result[0] if result else {}

    def clear_frequency(self, frequency: Timeframe):
        """
        Clear all KPIs for a specific frequency.

        Args:
            frequency (Timeframe): The frequency for which to clear all KPIs.
        """
        if frequency.value in self.data:
            self.data[frequency.value] = {}
