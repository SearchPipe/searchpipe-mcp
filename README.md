# SearchPipe Integrations

[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-blue)](https://modelcontextprotocol.io/)
[![SearchPipe](https://img.shields.io/badge/Powered%20by-SearchPipe-green)](https://searchpipe.tech)

Official integration packages for [SearchPipe](https://searchpipe.tech) — a web search API and MCP server for developers building AI agents.

This repository contains:

- **Remote MCP endpoint** — connect any MCP client to SearchPipe via Streamable HTTP (no local install needed)
- **[LangChain SDK](langchain-searchpipe/)** — `pip install langchain-searchpipe` for retriever, tool, and answer components
- **[Python SDK](sdks/python/)** — `pip install searchpipe`, official thin client over the Search API
- **[TypeScript SDK](sdks/typescript/)** — `npm install searchpipe`, official zero-dependency client (ESM + CJS)

> The SearchPipe server itself is a managed service at [searchpipe.tech](https://searchpipe.tech). Self-hosting is available on request.

## MCP Access (Remote)

Add to your MCP client config (Claude Desktop, Cursor, Windsurf, etc.):

```json
{
  "mcpServers": {
    "searchpipe": {
      "url": "https://searchpipe.tech/mcp/?api_key=sp-your-api-key-here"
    }
  }
}
```

Or use an Authorization header instead of URL parameter:

```json
{
  "mcpServers": {
    "searchpipe": {
      "url": "https://searchpipe.tech/mcp/",
      "headers": {
        "Authorization": "Bearer sp-your-api-key-here"
      }
    }
  }
}
```

See [`claude_desktop_config.json.example`](claude_desktop_config.json.example) for a ready-to-copy template.

## LangChain Integration

```bash
pip install langchain-searchpipe
```

See [langchain-searchpipe/README.md](langchain-searchpipe/README.md) for full usage examples (retriever, tool, answer components).

## Official SDKs

Both SDKs are thin wrappers over `POST /search` — same parameters, same response shape as the REST API.

**Python** ([sdks/python/](sdks/python/)):

```bash
pip install searchpipe
```

```python
from searchpipe import SearchPipe

client = SearchPipe(api_key="sp-YOUR_KEY")
resp = client.search("FastAPI tutorial", max_results=5, include_answer=True)
print(resp.answer)
for r in resp.results:
    print(r.score, r.title, r.url)
```

**JavaScript / TypeScript** ([sdks/typescript/](sdks/typescript/)):

```bash
npm install searchpipe
```

```ts
import { SearchPipe } from "searchpipe";

const client = new SearchPipe({ apiKey: "sp-YOUR_KEY" });
const resp = await client.search({ query: "FastAPI tutorial", maxResults: 5, includeAnswer: true });
console.log(resp.answer);
```

Both default to `https://searchpipe.tech` and read the key from `SEARCHPIPE_API_KEY`. See each SDK's README for the full API, error classes, and self-hosting options.

## Getting an API Key

1. Sign up at [searchpipe.tech](https://searchpipe.tech)
2. Verify your email
3. Go to Dashboard → API Keys → copy your `sp-` key
4. New accounts receive free credits to try the service

## Tool Schema

### `searchpipe_search`

Run a web search with optional AI-generated answer.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ | — | Search query |
| `max_results` | integer | — | 5 | Number of results (1–20) |
| `include_answer` | boolean | — | false | Include AI-generated answer |
| `include_raw_content` | boolean | — | false | Include full page content |
| `api_key` | string | — | — | API key (or use env var / URL param) |

**Returns**: Tavily-style `SearchResponse` with `query`, `answer`, `results[]`.

## Links

- **Website**: [searchpipe.tech](https://searchpipe.tech)
- **API Docs**: [searchpipe.tech/docs](https://searchpipe.tech/docs)
- **MCP Endpoint**: `https://searchpipe.tech/mcp/`

## License

MIT
