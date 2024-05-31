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

import json
from typing import Any, List, Optional, Dict
import uuid
import requests

from cloud_common import objects
from cloud_common.objects.mission import MissionObjectV1, MissionRouteNodeV1
from cloud_common.objects import common


class DatabaseClient:
    """A connection to the centralized database where all api objects are stored"""
    def __init__(self, url: str = "http://localhost:5000"):
        self._url = url
        self._publisher_id = str(uuid.uuid4())

    def create(self, obj: objects.ApiObject):
        url = f"{self._url}/{obj.get_alias()}"
        fields = json.loads(obj.spec.json())
        fields["name"] = obj.name
        response = requests.post(url, json=fields, params={"publisher_id": self._publisher_id})
        common.handle_response(response)

    def update_spec(self, obj: objects.ApiObject):
        url = f"{self._url}/{obj.get_alias()}/{obj.name}"
        response = requests.put(url, json=json.loads(obj.spec.json()),
                                params={"publisher_id": self._publisher_id})
        common.handle_response(response)

    def update_status(self, obj: objects.ApiObject):
        url = f"{self._url}/{obj.get_alias()}/{obj.name}"
        response = requests.put(url, json={"status": json.loads(obj.status.json())},
                                params={"publisher_id": self._publisher_id})
        common.handle_response(response)

    def list(self, object_type: Any, params: Optional[Dict] = None) -> List[objects.ApiObject]:
        url = f"{self._url}/{object_type.get_alias()}"
        response = requests.get(url, params=params)
        common.handle_response(response)
        return [object_type(**obj) for obj in json.loads(response.text)]

    def get(self, object_type: Any, name: str) -> objects.ApiObject:
        url = f"{self._url}/{object_type.get_alias()}/{name}"
        response = requests.get(url)
        common.handle_response(response)
        return object_type(**json.loads(response.text))

    def watch(self, object_type: Any):
        url = f"{self._url}/{object_type.get_alias()}/watch"
        response = requests.get(url, stream=True, params={"publisher_id": self._publisher_id})
        for i in response.iter_lines():
            yield object_type(**json.loads(i))

    def delete(self, object_type: Any, name: str):
        url = f"{self._url}/{object_type.get_alias()}/{name}"
        response = requests.delete(url)
        common.handle_response(response)

    def cancel_mission(self, name: str):
        url = f"{self._url}/{MissionObjectV1.get_alias()}/{name}/cancel"
        response = requests.post(url)
        common.handle_response(response)

    def update_mission(self, name: str, update_nodes: Dict[str, MissionRouteNodeV1]):
        url = f"{self._url}/{MissionObjectV1.get_alias()}/{name}/update"
        response = requests.post(url, json=update_nodes,
                                 params={"publisher_id": self._publisher_id})
        common.handle_response(response)

    def is_running(self, timeout: int = 5) -> bool:
        url = f"{self._url}/health"
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return True
        except requests.ConnectionError:
            return False
        except requests.Timeout:
            return False
        return False
