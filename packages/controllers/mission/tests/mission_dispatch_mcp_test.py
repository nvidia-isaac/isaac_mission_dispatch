#!/usr/bin/env python3
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

import unittest
import asyncio

from mcp.types import CallToolResult, TextContent
from packages.controllers.mission.tests import client as simulator
from packages.controllers.mission.tests import test_context
from src import server as mcp_server


TOOL_NAMES = {
    "test_mission_dispatch_connection",
    "get_robot_status",
    "get_mission_status",
    "get_robots_on_missions",
    "get_idle_robots",
    "get_fleet_summary",
    "check_robot_health",
    "get_mission_queue",
    "get_recent_failures",
    "create_robot",
    "dispatch_mission",
}


def _result_text(result: CallToolResult) -> str:
    assert result.content, "Expected tool result content to be non-empty"
    first = result.content[0]
    assert isinstance(first, TextContent), f"Expected TextContent, got {type(first)}"
    return first.text


class TestMissionDispatchMcpTools(unittest.IsolatedAsyncioTestCase):
    def _point_mcp_server_to_test_context(self, ctx: test_context.TestContext) -> None:
        mcp_server.base_url = ctx.md_url
        mcp_server.md_client.base_url = ctx.md_url

    async def _wait_for_dispatch_ready(self, timeout_s: float = 60.0) -> None:
        deadline = asyncio.get_running_loop().time() + timeout_s
        last_error = ""
        while asyncio.get_running_loop().time() < deadline:
            result = await mcp_server.call_tool("test_mission_dispatch_connection", {})
            if not result.isError:
                return
            last_error = _result_text(result)
            await asyncio.sleep(0.5)
        self.fail(
            f"Mission Dispatch MCP did not become ready in {timeout_s}s; "
            f"last error: {last_error}"
        )

    async def test_list_tools_contains_expected_tool_names(self) -> None:
        tools_result = await mcp_server.list_tools()
        names = {tool.name for tool in tools_result.tools}
        self.assertEqual(names, TOOL_NAMES)

    async def test_supported_tools_against_real_mission_dispatch(self) -> None:
        original_base_url = mcp_server.base_url
        original_client_base_url = mcp_server.md_client.base_url
        robot_name = "robot-mcp"
        robot = simulator.RobotInit(robot_name, 0, 0, 0)
        try:
            with test_context.TestContext([robot]) as ctx:
                self._point_mcp_server_to_test_context(ctx)
                await self._wait_for_dispatch_ready()

                connection_result = await mcp_server.call_tool("test_mission_dispatch_connection", {})
                self.assertFalse(connection_result.isError)
                self.assertIn("Mission Dispatch Connection OK", _result_text(connection_result))

                create_result = await mcp_server.call_tool("create_robot", {"name": robot_name})
                self.assertFalse(create_result.isError)
                self.assertIn("Robot Created Successfully", _result_text(create_result))
                self.assertIn(robot_name, _result_text(create_result))

                robot_status_result = await mcp_server.call_tool(
                    "get_robot_status", {"robot_name": robot_name}
                )
                self.assertFalse(robot_status_result.isError)
                self.assertIn(robot_name, _result_text(robot_status_result))

                fleet_result = await mcp_server.call_tool("get_fleet_summary", {})
                self.assertFalse(fleet_result.isError)
                self.assertIn("Mission Dispatch Fleet Dashboard", _result_text(fleet_result))

                dispatch_result = await mcp_server.call_tool(
                    "dispatch_mission",
                    {"robot": robot_name, "x": 1.0, "y": 2.0},
                )
                self.assertFalse(dispatch_result.isError)
                self.assertIn("Mission Dispatched Successfully", _result_text(dispatch_result))

                mission_status_result = await mcp_server.call_tool(
                    "get_mission_status", {"robot": robot_name}
                )
                self.assertFalse(mission_status_result.isError)
                self.assertIn(robot_name, _result_text(mission_status_result))
        finally:
            mcp_server.base_url = original_base_url
            mcp_server.md_client.base_url = original_client_base_url

    async def test_unknown_tool_returns_error(self) -> None:
        result = await mcp_server.call_tool("does_not_exist", {})
        self.assertTrue(result.isError)
        self.assertIn("Error: unknown tool: does_not_exist", _result_text(result))


if __name__ == "__main__":
    unittest.main()
