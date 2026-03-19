# Mission Dispatch MCP Tutorial (Cursor)

This tutorial explains how to run the Mission Dispatch MCP server from this repo and connect it to Cursor.

## Requirements

- Ubuntu/Linux environment (validated on Ubuntu 24.04)
- Python 3.10+
- Cursor installed (v2.4+ recommended)
- Install and launch Isaac Sim using the [Isaac ROS Isaac Sim Setup Guide](https://nvidia-isaac-ros.github.io/getting_started/index.html)
- Launch Mission Control services first using the [Mission Control Tutorial](https://github.com/nvidia-isaac/isaac_mission_control/blob/main/docs/tutorial/tutorial.md) (this bringup starts both Mission Control and Mission Dispatch)
- Isaac Sim setup and Mission Control service bringup can be done in parallel
- Mission Dispatch API reachable (default in MCP package: `http://localhost:5002`)

Quick health check:

```bash
curl http://localhost:5002/health
```

## 1) Set up the MCP package

From the repository root:

```bash
cd packages/agentic-utilities/mission-dispatch-mcp
python3 -m venv venv
./venv/bin/python -m pip install -U pip
./venv/bin/python -m pip install -e .
```

## 2) Configure Cursor MCP directly in `mcp.json`

Edit `~/.cursor/mcp.json` (or use Cursor Settings -> MCP and Integration, which writes this file).

Add/update this server entry with your real local paths:

```json
{
  "mcpServers": {
    "mission-dispatch": {
      "command": "bash",
      "args": [
        "-lc",
        "set -euo pipefail; cd \"/ABS/PATH/TO/mission_dispatch/packages/agentic-utilities/mission-dispatch-mcp\" && exec \"/ABS/PATH/TO/mission_dispatch/packages/agentic-utilities/mission-dispatch-mcp/venv/bin/python\" -m mission_dispatch_mcp.server"
      ],
      "env": {
        "MISSION_DISPATCH_URL": "http://localhost:5002"
      }
    }
  }
}
```

Notes:

- Replace `/ABS/PATH/TO/mission_dispatch` with your actual path.
- If your Mission Dispatch API is on a different host/port, update `MISSION_DISPATCH_URL`.
- No `.env` file is required for this flow.

## 3) Enable and verify in Cursor

- Open Cursor Settings -> MCP and Integration.
- Enable the `mission-dispatch` server.
- Start a new chat and ask:
  - `Use Mission Dispatch MCP to test the connection.`

If configured correctly, the server should respond with a successful connection result.

## 4) Troubleshooting

- **Connection refused**
  - Confirm Mission Dispatch API is reachable at the configured `MISSION_DISPATCH_URL`.
- **Tools do not appear**
  - Disable/re-enable the MCP server in Cursor settings.
  - Start a new chat.
  - Restart Cursor.
- **Check server logs**
  - `/tmp/mission_dispatch_mcp.log`

## Implementation references

- MCP server tools: `packages/agentic-utilities/mission-dispatch-mcp/src/server.py`
- Mission Dispatch API client used by the MCP server: `packages/agentic-utilities/mission-dispatch-mcp/src/queries.py`

