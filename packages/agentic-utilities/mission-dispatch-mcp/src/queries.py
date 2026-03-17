"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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

Database client for Mission Dispatch MCP

Handles communication with the Mission Dispatch REST API to retrieve
robot and mission status information.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


class MissionDispatchClientError(RuntimeError):
    """Base error raised by Mission Dispatch MCP client operations."""


class RobotNotFoundError(MissionDispatchClientError):
    """Raised when a robot does not exist in Mission Dispatch."""


class MissionDispatchClient:
    """Client for interacting with Mission Dispatch database API"""

    def __init__(self, base_url: str = "http://localhost:5002"):
        self.base_url = base_url

    def _request_json(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Any:
        """Make an HTTP request and return parsed JSON with consistent error handling."""
        url = f"{self.base_url}/{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise MissionDispatchClientError(
                f"Cannot connect to Mission Dispatch at {self.base_url}. Is the service running?"
            ) from e
        except requests.exceptions.Timeout as e:
            raise MissionDispatchClientError(
                f"Timeout connecting to Mission Dispatch at {self.base_url}"
            ) from e
        except requests.exceptions.HTTPError as e:
            raise MissionDispatchClientError(
                f"HTTP error {response.status_code}: {response.text}"
            ) from e

        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise MissionDispatchClientError("Invalid JSON response from Mission Dispatch API") from e

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> List[Dict]:
        """Make a GET request to the API with error handling."""
        return self._request_json("GET", endpoint, params=params)

    def _post_request(self, endpoint: str, data: Dict) -> Dict:
        """Make a POST request to the API with error handling."""
        return self._request_json("POST", endpoint, data=data)

    def create_robot(self, name: str, labels: Optional[Dict] = None) -> Dict:
        """Create a new robot in the database"""
        data = {"name": name}
        if labels:
            data["labels"] = labels
        return self._post_request("robot", data)

    def get_all_robots(self) -> List[Dict]:
        """Get all robots from the database"""
        return self._make_request("robot")

    def get_robot_by_name(self, name: str) -> Dict:
        """Get specific robot by name"""
        try:
            response = requests.get(f"{self.base_url}/robot/{name}", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 400:
                raise RobotNotFoundError(f"Robot '{name}' not found") from e
            raise MissionDispatchClientError(
                f"HTTP error {response.status_code}: {response.text}"
            ) from e

    def get_robots_by_state(self, state: str) -> List[Dict]:
        """Get robots filtered by state"""
        params = {"state": state}
        return self._make_request("robot", params=params)

    def get_online_robots(self) -> List[Dict]:
        """Get all online robots"""
        params = {"online": "true"}
        return self._make_request("robot", params=params)

    def get_offline_robots(self) -> List[Dict]:
        """Get all offline robots"""
        params = {"online": "false"}
        return self._make_request("robot", params=params)

    def get_robots_by_battery_range(
        self, min_battery: Optional[float] = None, max_battery: Optional[float] = None
    ) -> List[Dict]:
        """Get robots filtered by battery level range"""
        params: Dict[str, Any] = {}
        if min_battery is not None:
            params["min_battery"] = min_battery
        if max_battery is not None:
            params["max_battery"] = max_battery
        return self._make_request("robot", params=params)

    def get_all_missions(self) -> List[Dict]:
        """Get all missions from the database"""
        return self._make_request("mission")

    def get_missions(self, params: Optional[Dict] = None) -> List[Dict]:
        """Get missions with arbitrary query params.

        Server-side filtering/limiting is used when supported.
        """
        return self._make_request("mission", params=params)

    def get_missions_by_state(self, state: str) -> List[Dict]:
        """Get missions filtered by state"""
        params = {"state": state}
        return self._make_request("mission", params=params)

    def get_missions_by_robot(self, robot_name: str) -> List[Dict]:
        """Get missions for a specific robot"""
        params = {"robot": robot_name}
        return self._make_request("mission", params=params)

    def get_active_missions(self) -> List[Dict]:
        """Get all currently active missions (RUNNING and PENDING)"""
        all_missions = self.get_all_missions()
        return [
            m for m in all_missions if m.get("status", {}).get("state") in ["RUNNING", "PENDING"]
        ]

    def get_completed_missions(self) -> List[Dict]:
        """Get all completed missions"""
        return self.get_missions_by_state("COMPLETED")

    def get_failed_missions(self) -> List[Dict]:
        """Get all failed missions"""
        return self.get_missions_by_state("FAILED")

    def get_robot_with_current_mission(self, robot_name: str) -> Dict:
        """Get robot info along with its current active mission if any"""
        robot = self.get_robot_by_name(robot_name)
        missions = self.get_missions_by_robot(robot_name)
        active_missions = [
            m for m in missions if m.get("status", {}).get("state") in ["RUNNING", "PENDING"]
        ]

        return {"robot": robot, "current_missions": active_missions}

    def health_check(self) -> Dict:
        """Check if the Mission Dispatch API is accessible"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            response.raise_for_status()
            return {"status": "healthy", "api_accessible": True}
        except requests.exceptions.RequestException as e:
            return {"status": "unhealthy", "api_accessible": False, "error": str(e)}

    def dispatch_mission(
        self,
        robot: str,
        mission_tree: List[Dict],
        name: Optional[str] = None,
        timeout: int = 300,
        needs_canceled: bool = False,
    ) -> Dict:
        """Dispatch a mission to a robot"""
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=timeout)).isoformat()

        data = {
            "robot": robot,
            "mission_tree": mission_tree,
            "timeout": timeout,
            "deadline": deadline,
            "needs_canceled": needs_canceled,
            "name": name or "mission",
        }
        return self._post_request("mission", data)

    def dispatch_move_mission(
        self,
        robot: str,
        x: float,
        y: float,
        theta: float = 0.0,
        name: Optional[str] = None,
        timeout: int = 300,
        allowed_deviation_xy: float = 0.1,
        allowed_deviation_theta: float = 0.0,
    ) -> Dict:
        """Dispatch a simple move mission to navigate a robot to a pose"""
        mission_name = name or f"move_to_{x:.2f}_{y:.2f}"
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=timeout)).isoformat()

        waypoint = {
            "x": x,
            "y": y,
            "theta": theta,
            "map_id": "",
            "allowedDeviationXY": allowed_deviation_xy,
            "allowedDeviationTheta": allowed_deviation_theta,
        }

        data = {
            "robot": robot,
            "mission_tree": [
                {"name": mission_name, "parent": "root", "route": {"waypoints": [waypoint]}}
            ],
            "timeout": timeout,
            "deadline": deadline,
            "needs_canceled": False,
            "update_nodes": {
                "additionalProp1": {"waypoints": [waypoint]},
                "additionalProp2": {"waypoints": [waypoint]},
                "additionalProp3": {"waypoints": [waypoint]},
            },
            "name": mission_name,
        }
        return self._post_request("mission", data)
