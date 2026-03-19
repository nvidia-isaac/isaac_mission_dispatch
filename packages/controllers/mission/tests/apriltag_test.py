"""
SPDX-FileCopyrightText: NVIDIA CORPORATION & AFFILIATES
Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

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
from cloud_common.objects import mission as mission_object
from packages.controllers.mission.tests import client as simulator
from packages.controllers.mission.tests import test_context


class TestAprilTagDetection(unittest.TestCase):
    """Test AprilTag detection using mission simulator"""

    def test_apriltag_detection_action(self):
        """Test AprilTag detection action using mission simulator"""
        robot = simulator.RobotInit("test01", 0, 0, 0)

        with test_context.TestContext([robot]) as ctx:
            # Create the robot
            ctx.db_client.create(
                api_objects.RobotObjectV1(name="test01", status={}))
            time.sleep(0.25)

            # Verify robot exists
            self.assertGreater(
                len(ctx.db_client.list(api_objects.RobotObjectV1)), 0)

            # Create AprilTag detection mission
            apriltag_action = test_context.action_generator(
                params={},
                action_type="get_apriltags"
            )

            mission = test_context.mission_object_generator(
                robot="test01",
                mission_tree=[apriltag_action]
            )

            # Submit the mission
            ctx.db_client.create(mission)
            time.sleep(1.25) # Give the mission time to start

            # Wait for mission to complete
            mission_completed = False
            for update in ctx.db_client.watch(api_objects.MissionObjectV1):
                if update.status.state.done:
                    # Verify mission completed successfully
                    self.assertEqual(
                        update.status.state,
                        mission_object.MissionStateV1.COMPLETED
                    )
                    mission_completed = True
                    break

            self.assertTrue(mission_completed, "Mission should have completed")

            # Get AprilTag detection results from database
            apriltag_results = ctx.db_client.get(
                api_objects.AprilTagResultsObjectV1, "test01")

            # Verify results are correct
            self.assertIsNotNone(apriltag_results)
            self.assertEqual(apriltag_results.name, "test01")
            self.assertIsNotNone(apriltag_results.status)
            self.assertIsNotNone(apriltag_results.status.detected_apriltags)

            # Verify we have at least one AprilTag detected (mock data)
            self.assertGreater(
                len(apriltag_results.status.detected_apriltags), 0)

            # Verify the structure of the detected AprilTag
            detected_tag = apriltag_results.status.detected_apriltags[0]
            self.assertEqual(detected_tag.tag_id, 42)
            self.assertEqual(detected_tag.family, "tag36h11")
            self.assertEqual(detected_tag.frame_id, "camera_link")
            self.assertIsNotNone(detected_tag.center)
            self.assertIsNotNone(detected_tag.pose)
            self.assertIsInstance(detected_tag.timestamp, float)

            # Verify center coordinates
            self.assertEqual(detected_tag.center.x, 320.0)
            self.assertEqual(detected_tag.center.y, 240.0)

            # Verify pose structure
            self.assertIsNotNone(detected_tag.pose.position)
            self.assertIsNotNone(detected_tag.pose.orientation)

            print("AprilTag detection test passed successfully!")


if __name__ == '__main__':
    unittest.main()
