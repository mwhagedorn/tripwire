import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolRequestParams

import tripwire.mcp_server as mcp_server_module
from tripwire.eero_adapter import AuthenticationError
from tripwire.mcp_server import _scan, get_network_snapshot, mcp

NETWORKS_RESPONSE = {
    "meta": {"code": 200},
    "data": {"networks": [{"id": 1001, "name": "Home", "status": "connected"}]},
}
EEROS_RESPONSE = {"meta": {"code": 200}, "data": []}
PROFILES_RESPONSE = {"meta": {"code": 200}, "data": []}
DEVICES_RESPONSE = {
    "meta": {"code": 200},
    "data": [
        {
            "mac": "11:22:33:44:55:66",
            "nickname": "Mike's Phone",
            "hostname": "mikes-iphone",
            "display_name": "Mike's Phone",
            "connected": True,
            "wireless": True,
            "connection_type": "wireless",
            "source": {},
            "manufacturer": "Apple, Inc.",
            "ip": "192.168.1.50",
            "is_guest": False,
            "paused": False,
        }
    ],
}


class FakeAdapter:
    def __init__(self, *, authenticated: bool):
        self.is_authenticated = authenticated
        self.entered = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, *exc_info):
        pass

    async def get_networks(self):
        return NETWORKS_RESPONSE

    async def get_eeros(self, network_id):
        return EEROS_RESPONSE

    async def get_profiles(self, network_id):
        return PROFILES_RESPONSE

    async def get_devices(self, network_id):
        return DEVICES_RESPONSE


def test_scan_rejects_unauthenticated_adapter():
    adapter = FakeAdapter(authenticated=False)

    with pytest.raises(AuthenticationError):
        asyncio.run(_scan(adapter))

    assert adapter.entered is True


def test_scan_returns_the_full_snapshot_as_a_dict():
    adapter = FakeAdapter(authenticated=True)

    result = asyncio.run(_scan(adapter))

    assert set(result.keys()) == {"network", "nodes", "profiles", "devices"}
    assert result["network"]["id"] == "1001"
    assert result["network"]["name"] == "Home"
    assert result["devices"][0]["mac"] == "11:22:33:44:55:66"
    assert result["devices"][0]["nickname"] == "Mike's Phone"
    assert result["nodes"] == []
    assert result["profiles"] == []


def test_tool_translates_authentication_error_into_tool_error(monkeypatch):
    monkeypatch.setattr(
        mcp_server_module, "EeroClientAdapter", lambda cookie_file=None: FakeAdapter(authenticated=False)
    )

    with pytest.raises(ToolError) as exc_info:
        asyncio.run(get_network_snapshot())

    assert "Not logged in" in str(exc_info.value)


def test_tool_succeeds_end_to_end_with_a_fake_adapter(monkeypatch):
    monkeypatch.setattr(
        mcp_server_module, "EeroClientAdapter", lambda cookie_file=None: FakeAdapter(authenticated=True)
    )

    result = asyncio.run(get_network_snapshot())

    assert result["network"]["name"] == "Home"


def test_tool_error_survives_the_real_request_handling_path(monkeypatch):
    """Regression test: a plain AdapterError raised from a tool is swallowed
    by the mcp SDK into a generic 'Error executing tool X' message with no
    detail (see mcp.server.mcpserver.exceptions.UnexpectedToolError). The
    tool must translate AdapterError into the SDK's own ToolError so this
    message actually reaches the client."""
    monkeypatch.setattr(
        mcp_server_module, "EeroClientAdapter", lambda cookie_file=None: FakeAdapter(authenticated=False)
    )

    result = asyncio.run(
        mcp._handle_call_tool(None, CallToolRequestParams(name="get_network_snapshot", arguments={}))
    )

    assert result.is_error is True
    assert "Not logged in" in result.content[0].text
