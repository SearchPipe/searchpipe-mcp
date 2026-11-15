# searchpipe-mcp

SearchPipe MCP server for developers building AI agents — local stdio proxy over the
SearchPipe web search API.

`initialize` / `tools/list` work offline without an API key. Tool calls need
`SEARCHPIPE_API_KEY` (`sp-…` — create a free key at
https://searchpipe.tech/dashboard/api-keys) and run on the same commercial pipeline as
the REST API: authentication, rate limiting, moderation, per-call credit billing and
automatic refund on failure.

## Install & run

```bash
pip install "searchpipe-mcp @ git+https://github.com/SearchPipe/searchpipe-mcp.git#subdirectory=mcp-server"
SEARCHPIPE_API_KEY=sp-your-key searchpipe-mcp
```

Or with Docker (from the repository root):

```bash
docker build -t searchpipe-mcp .
docker run -i --rm -e SEARCHPIPE_API_KEY=sp-your-key searchpipe-mcp
```

Prefer zero local install? Use the remote endpoint directly:
`https://searchpipe.tech/mcp/` (Streamable HTTP, `Authorization: Bearer` header or
`?api_key=` URL parameter).

## Tools

| Tool | Endpoint | Notes |
| --- | --- | --- |
| `searchpipe_search` | `POST /search` | Ranked results with source URLs, optional AI answer; basic 1 credit / advanced 2 / fast 0.5 |
| `searchpipe_verify` | `POST /verify` | Four-label verdict with span-level quotes; typically 5-15 seconds |
| `searchpipe_account_balance` | `GET /v1/account/balance` | Free, no credits charged |
