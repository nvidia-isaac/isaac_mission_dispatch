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
"""

import datetime
import json
import unittest

from cloud_common.objects import mission
from cloud_common.objects import robot
from packages.controllers.mission import vda5050_types


class PydanticV2RegressionTest(unittest.TestCase):

    @staticmethod
    def _mission_spec(**kwargs):
        return mission.MissionSpecV1(
            robot="robot-1",
            mission_tree=[mission.MissionNodeV1(constant={})],
            **kwargs,
        )

    def test_timedeltas_keep_numeric_json_wire_format(self):
        deadline = datetime.datetime(2026, 9, 3, 12, 30, tzinfo=datetime.timezone.utc)
        mission_spec = self._mission_spec(
            timeout=datetime.timedelta(seconds=12.5), deadline=deadline
        )
        mission_json = json.loads(mission_spec.model_dump_json())
        robot_json = json.loads(robot.RobotSpecV1().model_dump_json())

        self.assertEqual(mission_json["timeout"], 12.5)
        self.assertEqual(robot_json["heartbeat_timeout"], 30.0)
        self.assertEqual(mission_json["deadline"], "2026-09-03T12:30:00Z")
        self.assertIsInstance(mission_spec.model_dump()["timeout"], datetime.timedelta)

    def test_timedelta_json_schema_keeps_numeric_api_contract(self):
        mission_timeout = mission.MissionSpecV1.model_json_schema(
            mode="serialization"
        )["properties"]["timeout"]
        robot_timeout = robot.RobotSpecV1.model_json_schema(
            mode="serialization"
        )["properties"]["heartbeat_timeout"]

        self.assertEqual(mission_timeout["type"], "number")
        self.assertEqual(mission_timeout["default"], 300.0)
        self.assertEqual(robot_timeout["type"], "number")
        self.assertEqual(robot_timeout["default"], 30.0)

    def test_api_object_inherits_timedelta_serialization(self):
        mission_object = mission.MissionObjectV1(
            name="mission-1",
            robot="robot-1",
            mission_tree=[mission.MissionNodeV1(constant={})],
            status={},
        )

        self.assertEqual(json.loads(mission_object.model_dump_json())["timeout"], 300.0)
        self.assertEqual(json.loads(mission_object.spec.model_dump_json())["timeout"], 300.0)

    def test_enum_dump_modes_match_pydantic_v1_behavior(self):
        status = mission.MissionStatusV1(
            state=mission.MissionStateV1.FAILED,
            failure_category=mission.MissionFailureCategoryV1.TIMEOUT,
        )
        python_dump = status.model_dump()
        json_dump = json.loads(status.model_dump_json())

        self.assertIs(python_dump["state"], mission.MissionStateV1.FAILED)
        self.assertIs(
            python_dump["failure_category"], mission.MissionFailureCategoryV1.TIMEOUT
        )
        self.assertEqual(json_dump["state"], "FAILED")
        self.assertEqual(json_dump["failure_category"], "TIMEOUT")

    def test_action_parameters_still_coerce_to_vda5050_strings(self):
        action = vda5050_types.VDA5050Action.from_mission_action(
            mission.MissionActionNodeV1(
                action_type="test", action_parameters={"count": 5, "enabled": True}
            ),
            node_id="node-1",
            mission_node_id=2,
        )

        self.assertEqual(action.param_dict, {"count": "5", "enabled": "True"})

    def test_optional_fields_remain_optional(self):
        self.assertEqual(
            mission.MissionQueryParamsV1().model_dump(),
            {
                "state": None,
                "started_after": None,
                "started_before": None,
                "robot": None,
                "most_recent": None,
            },
        )
        self.assertIsNone(
            vda5050_types.VDA5050Node(nodeId="node-1", sequenceId=0).nodePosition
        )

if __name__ == "__main__":
    unittest.main()
