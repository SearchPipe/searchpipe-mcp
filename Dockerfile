# SearchPipe MCP server (stdio) — builds the local stdio server defined in
# mcp-server/. Introspection (initialize, tools/list) works without an API key;
# tool calls need SEARCHPIPE_API_KEY passed via the environment.
FROM python:3.13-slim

WORKDIR /app
COPY mcp-server /app/mcp-server
RUN pip install --no-cache-dir /app/mcp-server

ENV SEARCHPIPE_BASE_URL=https://searchpipe.tech
ENTRYPOINT ["searchpipe-mcp"]
