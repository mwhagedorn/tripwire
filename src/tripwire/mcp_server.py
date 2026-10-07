"""MCP server exposing live Eero network config data as read-only tools.

Reuses the CLI's stored session (same cookie_file as `tripwire login`) and
the Scanner, so there is no separate auth flow or data path for MCP clients.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .eero_adapter import AdapterError, AuthenticationError, EeroAdapter, EeroClientAdapter
from .scanner import Scanner, snapshot_to_dict

mcp = MCPServer("tripwire")


def _session_path() -> Path:
    return Path.home() / ".tripwire" / "session"


async def _scan(adapter: EeroAdapter) -> dict[str, Any]:
    async with adapter:
        if not adapter.is_authenticated:
            raise AuthenticationError(
                "Not logged in. Run `tripwire login` and `tripwire verify` first."
            )
        snapshot = await Scanner(adapter).scan()
    return snapshot_to_dict(snapshot)


@mcp.tool()
async def get_network_snapshot() -> dict[str, Any]:
    """Return the current Eero network's full state: the network itself, its
    physical nodes, its profiles/groups, and every connected device."""
    adapter = EeroClientAdapter(cookie_file=str(_session_path()))
    try:
        return await _scan(adapter)
    except AdapterError as exc:
        # Translate to the mcp SDK's own ToolError: anything else raised from
        # a tool is treated as a crash and the message never reaches the
        # client (see mcp.server.mcpserver.exceptions.UnexpectedToolError).
        raise ToolError(str(exc)) from exc


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
