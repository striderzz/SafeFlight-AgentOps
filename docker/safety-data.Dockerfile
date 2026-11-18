FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/striderzz/SafeFlight-AgentOps" \
      org.opencontainers.image.description="SafeFlight safety-data MCP server"

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    MCP_HOST=0.0.0.0 MCP_PORT=8101
WORKDIR /app
COPY requirements-mcp.txt .
RUN pip install -r requirements-mcp.txt
COPY mcp_servers/__init__.py mcp_servers/__init__.py
COPY mcp_servers/safety_data ./mcp_servers/safety_data
RUN useradd --create-home --uid 1000 app
USER app
EXPOSE 8101
CMD ["python", "-m", "mcp_servers.safety_data.server"]
