"""live-signals MCP server (FastMCP, streamable HTTP).

Phase 1 skeleton: only `server_info`. `airport_weather` (aviationweather.gov) and
`recent_route_activity` (OpenSky) arrive in Phase 5.
"""

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "live-signals",
    instructions="Current airport weather and recent flight activity on a route.",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "8102")),
    stateless_http=True,
)


@mcp.tool()
def server_info() -> dict:
    """Name, version and available data sources of this server."""
    return {"server": "live-signals", "version": "0.1.0", "sources": []}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
