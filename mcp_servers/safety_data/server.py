"""safety-data MCP server (FastMCP, streamable HTTP).

Phase 1 skeleton: only `server_info`. The DuckDB tools (`carrier_accidents`,
`carrier_exposure`, `aircraft_type_record`, `search_accident_reports`,
`conflict_bulletins`, `track_crosses`) arrive in Phases 4 and 5.
"""

import os

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "safety-data",
    instructions="Read-only airline safety records, accident reports and airspace bulletins.",
    host=os.getenv("MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_PORT", "8101")),
    stateless_http=True,
)


@mcp.tool()
def server_info() -> dict:
    """Name, version and available data sources of this server."""
    return {"server": "safety-data", "version": "0.1.0", "sources": []}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
