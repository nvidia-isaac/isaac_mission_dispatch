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

Mission Dispatch MCP Server

Provides a Model Context Protocol (MCP) server for querying Mission Dispatch
robot and mission status information.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Callable, Dict, List

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from .queries import MissionDispatchClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger(__name__)

# Initialize the mission dispatch client with environment variable support
base_url = os.getenv("MISSION_DISPATCH_URL", "http://localhost:5002")
md_client = MissionDispatchClient(base_url)

# Create MCP server
server = Server("mission-dispatch-mcp")
TOOL_GET_ROBOT_STATUS = "get_robot_status"
TOOL_GET_MISSION_STATUS = "get_mission_status"
TOOL_GET_ROBOTS_ON_MISSIONS = "get_robots_on_missions"
TOOL_GET_IDLE_ROBOTS = "get_idle_robots"
TOOL_GET_FLEET_SUMMARY = "get_fleet_summary"
TOOL_CHECK_ROBOT_HEALTH = "check_robot_health"
TOOL_GET_MISSION_QUEUE = "get_mission_queue"
TOOL_GET_RECENT_FAILURES = "get_recent_failures"
TOOL_TEST_CONNECTION = "test_mission_dispatch_connection"
TOOL_CREATE_ROBOT = "create_robot"
TOOL_DISPATCH_MISSION = "dispatch_mission"


def _text_result(text: str, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], isError=is_error)


def _require(arguments: dict, key: str) -> Any:
    value = arguments.get(key)
    if value is None or value == "":
        raise ValueError(f"Missing required argument: {key}")
    return value


def format_robot_info(robot: Dict) -> str:
    """Format robot information for display."""
    status = robot.get("status", {})
    state = status.get("state", "UNKNOWN")
    online = status.get("online", False)
    battery = status.get("battery_level", 0)

    result = f"**{robot.get('name', 'unknown')}**\n"
    result += f"- State: {state}\n"
    result += f"- Online: {online}\n"
    result += f"- Battery: {battery:.1f}%\n"

    pose = status.get("pose", {})
    if pose and pose.get("x") is not None:
        result += f"- Position: ({pose.get('x', 0):.2f}, {pose.get('y', 0):.2f})\n"

    errors = status.get("errors", {})
    if errors:
        error_list = ", ".join(errors.keys()) if isinstance(errors, dict) else str(errors)
        result += f"- Errors: {error_list}\n"

    return result


def format_mission_info(mission: Dict) -> str:
    """Format mission information for display."""
    status = mission.get("status", {})
    state = status.get("state", "UNKNOWN")

    result = f"**{mission.get('name', 'unknown')}**\n"
    result += f"- State: {state}\n"
    result += f"- Robot: {mission.get('robot', 'Unknown')}\n"

    if status.get("start_timestamp"):
        result += f"- Started: {status.get('start_timestamp')}\n"
    if status.get("end_timestamp"):
        result += f"- Ended: {status.get('end_timestamp')}\n"
    if status.get("failure_reason"):
        result += f"- Failure: {status.get('failure_reason')}\n"
    if status.get("failure_category"):
        result += f"- Failure category: {status.get('failure_category')}\n"

    return result


@server.list_tools()
async def list_tools() -> ListToolsResult:
    """List available MCP tools for Mission Dispatch queries."""
    return ListToolsResult(
        tools=[
            Tool(
                name=TOOL_GET_ROBOT_STATUS,
                description="Get robot status for all robots or filter by state/name",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["IDLE", "ON_TASK", "CHARGING", "MAP_DEPLOYMENT", "TELEOP"],
                            "description": "Filter robots by state (optional)",
                        },
                        "robot_name": {
                            "type": "string",
                            "description": "Get status for specific robot by name (optional)",
                        },
                    },
                },
            ),
            Tool(
                name=TOOL_GET_MISSION_STATUS,
                description="Get missions and their status (optionally filter by state or robot)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "state": {
                            "type": "string",
                            "enum": ["PENDING", "RUNNING", "COMPLETED", "CANCELED", "FAILED"],
                            "description": "Filter missions by state (optional)",
                        },
                        "robot": {
                            "type": "string",
                            "description": "Filter missions for specific robot (optional)",
                        },
                    },
                },
            ),
            Tool(
                name=TOOL_GET_ROBOTS_ON_MISSIONS,
                description=(
                    "Get all robots currently executing missions (ON_TASK) with mission details"
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name=TOOL_GET_IDLE_ROBOTS,
                description="Get all robots that are idle and available for new missions",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name=TOOL_GET_FLEET_SUMMARY,
                description="Get a summary of robot and mission states (dashboard view)",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name=TOOL_CHECK_ROBOT_HEALTH,
                description="Check robot health (battery, online status, errors)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "min_battery": {
                            "type": "number",
                            "description": (
                                "Only show robots with battery below this threshold (optional)"
                            ),
                        }
                    },
                },
            ),
            Tool(
                name=TOOL_GET_MISSION_QUEUE,
                description="Get pending missions waiting to be executed",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name=TOOL_GET_RECENT_FAILURES,
                description="Get recently failed missions with failure reasons",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name=TOOL_TEST_CONNECTION,
                description="Test connection to Mission Dispatch API",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name=TOOL_CREATE_ROBOT,
                description="Create a new robot in the Mission Dispatch database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the robot to create (required)",
                        },
                        "labels": {
                            "type": "object",
                            "description": "Optional labels/metadata for the robot",
                        },
                    },
                    "required": ["name"],
                },
            ),
            Tool(
                name=TOOL_DISPATCH_MISSION,
                description="Dispatch a mission to send a robot to a location (x, y coordinates)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "robot": {
                            "type": "string",
                            "description": "Name of the robot to dispatch (required)",
                        },
                        "x": {"type": "number", "description": "Target x coordinate (required)"},
                        "y": {"type": "number", "description": "Target y coordinate (required)"},
                        "theta": {
                            "type": "number",
                            "description": "Target orientation in radians (optional, default 0.0)",
                        },
                        "mission_name": {
                            "type": "string",
                            "description": "Optional name for the mission",
                        },
                    },
                    "required": ["robot", "x", "y"],
                },
            ),
        ]
    )


def _handle_test_connection(_: dict) -> CallToolResult:
    health = md_client.health_check()
    if health.get("api_accessible"):
        try:
            robots = md_client.get_all_robots()
            missions = md_client.get_all_missions()
            result = "**Mission Dispatch Connection OK**\n\n"
            result += f"- API URL: {base_url}\n"
            result += f"- Robots in database: {len(robots)}\n"
            result += f"- Missions in database: {len(missions)}\n"
            result += "- Status: Healthy\n"
        except Exception as e:
            result = "**Connection Partial**\n\n"
            result += f"- API URL: {base_url}\n"
            result += "- Health endpoint: OK\n"
            result += f"- Data access: Failed ({e})\n"
        return _text_result(result)

    result = "**Mission Dispatch Connection Failed**\n\n"
    result += f"- API URL: {base_url}\n"
    result += f"- Error: {health.get('error', 'Unknown')}\n"
    result += "- Make sure Mission Dispatch services are running\n"
    return _text_result(result, is_error=True)


def _handle_get_robot_status(arguments: dict) -> CallToolResult:
    state = arguments.get("state")
    robot_name = arguments.get("robot_name")

    if robot_name:
        robot = md_client.get_robot_by_name(robot_name)
        result = f"**Robot {robot_name} Status**\n\n"
        result += format_robot_info(robot)
        return _text_result(result)

    if state:
        robots = md_client.get_robots_by_state(state)
        result = f"**Robots in {state} state**\n\n"
    else:
        robots = md_client.get_all_robots()
        result = "**All Robots**\n\n"

    if not robots:
        result += "No robots found.\n"
    else:
        for robot in robots:
            result += format_robot_info(robot) + "\n"
    return _text_result(result)


def _handle_get_mission_status(arguments: dict) -> CallToolResult:
    state = arguments.get("state")
    robot = arguments.get("robot")

    if robot:
        missions = md_client.get_missions_by_robot(robot)
        result = f"**Missions for robot {robot}**\n\n"
    elif state:
        missions = md_client.get_missions_by_state(state)
        result = f"**Missions in {state} state**\n\n"
    else:
        missions = md_client.get_all_missions()
        result = "**All Missions**\n\n"

    if not missions:
        result += "No missions found.\n"
    else:
        for mission in missions:
            result += format_mission_info(mission) + "\n"
    return _text_result(result)


def _handle_get_robots_on_missions(_: dict) -> CallToolResult:
    robots = md_client.get_robots_by_state("ON_TASK")
    result = "**Robots Currently On Missions**\n\n"

    if not robots:
        result += "No robots are currently on missions.\n"
        return _text_result(result)

    for robot in robots:
        result += format_robot_info(robot)
        try:
            missions = md_client.get_missions_by_robot(robot["name"])
            active = [
                m
                for m in missions
                if m.get("status", {}).get("state") in ["RUNNING", "PENDING"]
            ]
            if active:
                result += "Current missions:\n"
                for mission in active:
                    state = mission.get("status", {}).get("state", "UNKNOWN")
                    result += f"- {mission.get('name', 'unknown')} ({state})\n"
        except Exception as e:
            result += f"Could not retrieve mission info: {e}\n"
        result += "\n"

    return _text_result(result)


def _handle_get_idle_robots(_: dict) -> CallToolResult:
    robots = md_client.get_robots_by_state("IDLE")
    result = "**Idle Robots Available for Missions**\n\n"

    if not robots:
        result += "No robots are currently idle.\n"
        return _text_result(result)

    online_count = 0
    for robot in robots:
        result += format_robot_info(robot) + "\n"
        if robot.get("status", {}).get("online", False):
            online_count += 1
    result += f"Summary: {len(robots)} idle robots ({online_count} online)\n"
    return _text_result(result)


def _handle_get_fleet_summary(_: dict) -> CallToolResult:
    all_robots = md_client.get_all_robots()
    all_missions = md_client.get_all_missions()

    robot_states: Dict[str, list] = {}
    online_count = 0
    total_battery = 0.0
    battery_count = 0

    for robot in all_robots:
        state = robot.get("status", {}).get("state", "UNKNOWN")
        robot_states.setdefault(state, []).append(robot)
        if robot.get("status", {}).get("online", False):
            online_count += 1
        battery = robot.get("status", {}).get("battery_level", 0)
        if battery > 0:
            total_battery += float(battery)
            battery_count += 1

    mission_states: Dict[str, list] = {}
    for mission in all_missions:
        state = mission.get("status", {}).get("state", "UNKNOWN")
        mission_states.setdefault(state, []).append(mission)

    result = "**Mission Dispatch Fleet Dashboard**\n\n"
    result += "## Robot Fleet Status\n"
    for state in sorted(robot_states.keys()):
        result += f"- {state}: {len(robot_states[state])} robots\n"

    result += "\nFleet summary:\n"
    result += f"- Total robots: {len(all_robots)}\n"
    if all_robots:
        pct = (online_count / len(all_robots)) * 100.0
        result += f"- Online: {online_count} ({pct:.1f}%)\n"
    if battery_count > 0:
        avg_battery = total_battery / battery_count
        result += f"- Average battery: {avg_battery:.1f}%\n"

    result += "\n## Mission Status\n"
    for state in sorted(mission_states.keys()):
        result += f"- {state}: {len(mission_states[state])} missions\n"

    active = len(mission_states.get("RUNNING", [])) + len(mission_states.get("PENDING", []))
    result += "\nMission summary:\n"
    result += f"- Total missions: {len(all_missions)}\n"
    result += f"- Currently active: {active}\n"
    return _text_result(result)


def _collect_robot_health_buckets(
    robots: List[Dict], min_battery: float
) -> tuple[list[str], list[tuple[str, float]], list[tuple[str, object]], list[str]]:
    offline: list[str] = []
    low_battery: list[tuple[str, float]] = []
    with_errors: list[tuple[str, object]] = []
    healthy: list[str] = []

    for robot in robots:
        status = robot.get("status", {})
        name = robot.get("name", "unknown")
        online = bool(status.get("online", False))
        battery = float(status.get("battery_level", 0) or 0)
        errors = status.get("errors", {})

        if not online:
            offline.append(name)
        if online and battery < min_battery:
            low_battery.append((name, battery))
        if errors:
            with_errors.append((name, errors))
        if online and battery >= min_battery and not errors:
            healthy.append(name)

    return offline, low_battery, with_errors, healthy


def _format_robot_health_sections(
    *,
    offline: list[str],
    low_battery: list[tuple[str, float]],
    with_errors: list[tuple[str, object]],
    healthy: list[str],
    min_battery: float,
) -> str:
    sections = [
        _format_named_robot_section("Offline robots", offline),
        _format_low_battery_section(low_battery, min_battery),
        _format_error_section(with_errors),
        _format_healthy_section(healthy),
    ]
    result = "".join(section for section in sections if section)

    if not (offline or low_battery or with_errors):
        result += "All robots are healthy.\n\n"

    return result


def _format_named_robot_section(title: str, robots: list[str]) -> str:
    if not robots:
        return ""
    lines = [f"{title} ({len(robots)}):\n"]
    lines.extend(f"- {robot_name}\n" for robot_name in robots)
    lines.append("\n")
    return "".join(lines)


def _format_low_battery_section(low_battery: list[tuple[str, float]], min_battery: float) -> str:
    if not low_battery:
        return ""
    lines = [f"Low battery robots (< {min_battery}%, {len(low_battery)}):\n"]
    lines.extend(f"- {robot_name}: {battery:.1f}%\n" for robot_name, battery in low_battery)
    lines.append("\n")
    return "".join(lines)


def _format_error_section(with_errors: list[tuple[str, object]]) -> str:
    if not with_errors:
        return ""
    lines = [f"Robots with errors ({len(with_errors)}):\n"]
    for robot_name, errors in with_errors:
        error_list = ", ".join(errors.keys()) if isinstance(errors, dict) else str(errors)
        lines.append(f"- {robot_name}: {error_list}\n")
    lines.append("\n")
    return "".join(lines)


def _format_healthy_section(healthy: list[str]) -> str:
    if not healthy:
        return ""
    lines = [f"Healthy robots ({len(healthy)}):\n"]
    lines.extend(f"- {robot_name}\n" for robot_name in healthy[:5])
    if len(healthy) > 5:
        lines.append(f"- ... and {len(healthy) - 5} more\n")
    lines.append("\n")
    return "".join(lines)


def _handle_check_robot_health(arguments: dict) -> CallToolResult:
    min_battery = float(arguments.get("min_battery", 20.0))
    robots = md_client.get_all_robots()
    offline, low_battery, with_errors, healthy = _collect_robot_health_buckets(robots, min_battery)

    result = "**Robot Health Check**\n\n"
    result += _format_robot_health_sections(
        offline=offline,
        low_battery=low_battery,
        with_errors=with_errors,
        healthy=healthy,
        min_battery=min_battery,
    )

    issues = len(offline) + len(low_battery) + len(with_errors)
    result += "Health summary:\n"
    result += f"- Healthy: {len(healthy)}/{len(robots)}\n"
    result += f"- Issues: {issues}\n"
    return _text_result(result)


def _handle_get_mission_queue(_: dict) -> CallToolResult:
    pending = md_client.get_missions_by_state("PENDING")
    result = "**Mission Queue (Pending Missions)**\n\n"
    if not pending:
        result += "No missions currently pending.\n"
    else:
        result += f"Found {len(pending)} pending missions:\n\n"
        for mission in pending:
            result += format_mission_info(mission) + "\n"
    return _text_result(result)


def _handle_get_recent_failures(_: dict) -> CallToolResult:
    failed = md_client.get_failed_missions()
    result = "**Recent Mission Failures**\n\n"
    if not failed:
        result += "No failed missions found.\n"
    else:
        result += f"Found {len(failed)} failed missions:\n\n"
        for mission in failed:
            result += format_mission_info(mission) + "\n"
    return _text_result(result)


def _handle_create_robot(arguments: dict) -> CallToolResult:
    robot_name = _require(arguments, "name")
    labels = arguments.get("labels")
    robot = md_client.create_robot(robot_name, labels)
    result = "**Robot Created Successfully**\n\n"
    result += format_robot_info(robot)
    return _text_result(result)


def _handle_dispatch_mission(arguments: dict) -> CallToolResult:
    robot_name = _require(arguments, "robot")
    x = _require(arguments, "x")
    y = _require(arguments, "y")
    theta = float(arguments.get("theta", 0.0))
    mission_name = arguments.get("mission_name")

    mission = md_client.dispatch_move_mission(robot_name, x, y, theta, mission_name)
    result = "**Mission Dispatched Successfully**\n\n"
    result += format_mission_info(mission)
    result += f"\nTarget: ({float(x):.2f}, {float(y):.2f}) @ {theta:.2f} rad\n"
    return _text_result(result)


ToolHandler = Callable[[dict], CallToolResult]

_TOOL_HANDLERS: Dict[str, ToolHandler] = {
    TOOL_TEST_CONNECTION: _handle_test_connection,
    TOOL_GET_ROBOT_STATUS: _handle_get_robot_status,
    TOOL_GET_MISSION_STATUS: _handle_get_mission_status,
    TOOL_GET_ROBOTS_ON_MISSIONS: _handle_get_robots_on_missions,
    TOOL_GET_IDLE_ROBOTS: _handle_get_idle_robots,
    TOOL_GET_FLEET_SUMMARY: _handle_get_fleet_summary,
    TOOL_CHECK_ROBOT_HEALTH: _handle_check_robot_health,
    TOOL_GET_MISSION_QUEUE: _handle_get_mission_queue,
    TOOL_GET_RECENT_FAILURES: _handle_get_recent_failures,
    TOOL_CREATE_ROBOT: _handle_create_robot,
    TOOL_DISPATCH_MISSION: _handle_dispatch_mission,
}


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    """Handle MCP tool calls."""
    try:
        logger.info("Calling tool %s with args: %s", name, arguments)
        handler = _TOOL_HANDLERS.get(name)
        if handler is None:
            return _text_result(f"Error: unknown tool: {name}\n", is_error=True)
        return handler(arguments or {})
    except ValueError as e:
        return _text_result(f"Error: {e}\n", is_error=True)
    except Exception as e:
        logger.exception("Error in tool %s", name)
        error_msg = str(e)
        if "Cannot connect" in error_msg:
            error_msg += "\n\nTroubleshooting:\n"
            error_msg += "- Check if Mission Dispatch database is running\n"
            error_msg += "- Check if Mission Dispatch controller is running\n"
            error_msg += f"- Verify the API is accessible: `curl {base_url}/health`\n"
        return _text_result(f"Error: {error_msg}\n", is_error=True)


async def _main_async() -> None:
    """Async main entry point for the MCP server."""
    logger.info("Starting Mission Dispatch MCP server, connecting to %s", base_url)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="mission-dispatch-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Console-script entry point."""
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
