import asyncio

from fastapi.testclient import TestClient

from mcp_servers.live_signals.server import mcp as live_signals
from mcp_servers.safety_data.server import mcp as safety_data
from safeflight.api.app import app


def test_api_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_mcp_servers_expose_their_tools():
    for server, name in ((safety_data, "safety-data"), (live_signals, "live-signals")):
        tools = asyncio.run(server.list_tools())
        assert [t.name for t in tools] == ["server_info"]
        assert server.name == name
