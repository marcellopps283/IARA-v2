"""
mcp_client.py — MCP (Model Context Protocol) Client for IARA
Uses the official MCP SDK with stdio transport (native Linux, no REST workaround).
Manages connections to MCP servers and exposes their tools to the LLM.
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger("mcp_client")

# Registry of configured MCP servers
# Format: {"server_name": {"command": "npx", "args": [...], "env": {...}}}
_server_configs: dict[str, dict] = {}
_active_sessions: dict[str, Any] = {}


def register_server(name: str, command: str, args: list[str] | None = None, env: dict | None = None):
    """Register an MCP server configuration."""
    _server_configs[name] = {
        "command": command,
        "args": args or [],
        "env": env or {},
    }
    logger.info(f"🔌 MCP server '{name}' registered: {command} {' '.join(args or [])}")


async def _get_session(server_name: str):
    """Get or create an MCP session for a server."""
    if server_name in _active_sessions:
        return _active_sessions[server_name]

    if server_name not in _server_configs:
        raise ValueError(f"MCP server '{server_name}' not registered")

    config = _server_configs[server_name]

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=config["command"],
            args=config["args"],
            env=config.get("env"),
        )

        # Create persistent connection
        read_stream, write_stream = await stdio_client(server_params).__aenter__()
        session = ClientSession(read_stream, write_stream)
        await session.__aenter__()
        await session.initialize()

        _active_sessions[server_name] = {
            "session": session,
            "config": config,
        }

        logger.info(f"✅ MCP session '{server_name}' established")
        return _active_sessions[server_name]

    except Exception as e:
        logger.error(f"❌ Failed to connect to MCP server '{server_name}': {e}")
        raise


async def list_tools(server_name: str | None = None) -> list[dict]:
    """
    List available tools from MCP servers.
    If server_name is None, lists tools from all registered servers.
    Returns tools in OpenAI function calling format.
    """
    tools = []

    servers = [server_name] if server_name else list(_server_configs.keys())

    for name in servers:
        try:
            session_data = await _get_session(name)
            session = session_data["session"]

            result = await session.list_tools()

            for tool in result.tools:
                # Convert MCP tool format to OpenAI function calling format
                safe_name = f"mcp__{name}__{tool.name}".replace("-", "_")
                tools.append({
                    "type": "function",
                    "function": {
                        "name": safe_name,
                        "description": tool.description or f"MCP tool from {name}",
                        "parameters": tool.inputSchema if hasattr(tool, 'inputSchema') else {"type": "object", "properties": {}},
                    },
                    "_mcp_server": name,
                    "_mcp_tool": tool.name,
                })

            logger.info(f"🔌 {name}: {len(result.tools)} tools available")

        except Exception as e:
            logger.warning(f"⚠️ Could not list tools from '{name}': {e}")

    return tools


async def call_tool(server_name: str, tool_name: str, arguments: dict | None = None) -> str:
    """Call a specific tool on an MCP server."""
    try:
        session_data = await _get_session(server_name)
        session = session_data["session"]

        result = await session.call_tool(tool_name, arguments or {})

        # Combine all content blocks into a single text
        output_parts = []
        for content in result.content:
            if hasattr(content, "text"):
                output_parts.append(content.text)
            elif hasattr(content, "data"):
                output_parts.append(f"[Binary data: {len(content.data)} bytes]")
            else:
                output_parts.append(str(content))

        return "\n".join(output_parts) or "[No output]"

    except Exception as e:
        logger.error(f"❌ MCP tool call failed ({server_name}.{tool_name}): {e}")
        return f"Error: {e}"


async def close_all():
    """Close all active MCP sessions."""
    for name, session_data in _active_sessions.items():
        try:
            session = session_data["session"]
            await session.__aexit__(None, None, None)
            logger.info(f"🔌 MCP session '{name}' closed")
        except Exception:
            pass
    _active_sessions.clear()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Default server registrations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def init_default_servers():
    """Register default MCP servers available on the VPS."""
    # Fetch — HTTP content reader (replaces jina_reader_skill)
    register_server(
        "fetch",
        command="uvx",
        args=["mcp-server-fetch"],
    )

    # Filesystem — read/write files in the workspace
    register_server(
        "filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/opt/iara"],
    )

    logger.info("🔌 Default MCP servers registered")
