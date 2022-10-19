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

import json
from typing import Any, List
import uuid

import requests

from packages import objects
from packages.objects.mission import MissionObjectV1


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
        if response.status_code != 200:
            raise ValueError(response.text)

    def update_spec(self, obj: objects.ApiObject):
        url = f"{self._url}/{obj.get_alias()}/{obj.name}"
        response = requests.put(url, json=json.loads(obj.spec.json()),
                                params={"publisher_id": self._publisher_id})
        if response.status_code != 200:
            raise ValueError(response.text)

    def update_status(self, obj: objects.ApiObject):
        url = f"{self._url}/{obj.get_alias()}/{obj.name}"
        response = requests.put(url, json={"status": json.loads(obj.status.json())},
                                params={"publisher_id": self._publisher_id})
        if response.status_code != 200:
            raise ValueError(response.text)

    def list(self, object_type: Any) -> List[objects.ApiObject]:
        url = f"{self._url}/{object_type.get_alias()}"
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(response.text)
        return [object_type(**obj) for obj in json.loads(response.text)]

    def get(self, object_type: Any, name: str) -> objects.ApiObject:
        url = f"{self._url}/{object_type.get_alias()}/{name}"
        response = requests.get(url)
        if response.status_code != 200:
            raise ValueError(response.text)
        return object_type(**json.loads(response.text))

    def watch(self, object_type: Any):
        url = f"{self._url}/{object_type.get_alias()}/watch"
        response = requests.get(url, stream=True, params={"publisher_id": self._publisher_id})
        for i in response.iter_lines():
            yield object_type(**json.loads(i))

    def delete(self, object_type: Any, name: str):
        url = f"{self._url}/{object_type.get_alias()}/{name}"
        response = requests.delete(url)
        if response.status_code != 200:
            raise ValueError(response.text)

    def cancel_mission(self, name: str):
        url = f"{self._url}/{MissionObjectV1.get_alias()}/{name}/cancel"
        response = requests.post(url)
        if response.status_code != 200:
            raise ValueError(response.text)
