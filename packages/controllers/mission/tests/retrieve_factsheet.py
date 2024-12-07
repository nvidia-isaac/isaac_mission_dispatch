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
import time
import unittest

from cloud_common import objects as api_objects
from packages.controllers.mission.tests import client as simulator
from cloud_common.objects import mission as mission_object
from cloud_common.objects import robot as robot_object
from cloud_common.objects import common

from packages.controllers.mission.tests import test_context


class TestRetrieveFactsheet(unittest.TestCase):

    def test_retrieve_factsheet(self):
        """ Test if factsheet retrieval is functional """

        robot_arm = simulator.RobotInit("test01", 0, 0, 0, robot_type="arm")
        robot_amr = simulator.RobotInit("test02", 0, 0, 0, robot_type="amr")
        with test_context.TestContext([robot_arm, robot_amr], tick_period=1.0) as ctx:

            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            time.sleep(2)
            factsheet = ctx.db_client.get(robot_object.RobotObjectV1, "test01").status.factsheet

            assert (factsheet.agv_class == "FORKLIFT")

            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test02", status={}))
            time.sleep(0.25)
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 1)

            time.sleep(2)
            factsheet = ctx.db_client.get(robot_object.RobotObjectV1, "test02").status.factsheet

            assert (factsheet.agv_class == "CARRIER")


if __name__ == "__main__":
    unittest.main()
