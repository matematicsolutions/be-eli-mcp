# Dockerfile — lets Glama (or any sandbox) build and introspect this MCP server.
# The server is published on PyPI; this installs it and runs its stdio entrypoint.
FROM python:3.11-slim
RUN pip install --no-cache-dir be-eli-mcp
ENTRYPOINT ["be-eli-mcp"]
