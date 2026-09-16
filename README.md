# SearchPipe MCP Server

[![MCP](https://img.shields.io/badge/MCP-Streamable%20HTTP-blue)](https://modelcontextprotocol.io/)
[![SearchPipe](https://img.shields.io/badge/Powered%20by-SearchPipe-green)](https://searchpipe.tech)

MCP server for [SearchPipe](https://searchpipe.tech) — an AI-powered web search API (Tavily-style) that aggregates SearXNG multi-engine retrieval, trafilatura content extraction, and LLM reranking/summarization into a single `web_search` tool.

## Features

- **One tool, full pipeline**: `searchpipe_search` runs SearXNG retrieval → page fetching → LLM reranking → optional AI answer
- **Tavily-style structured output**: query, answer, results[] with title/url/content/score
- **Credit-based billing**: per-call credit deduction with automatic refund on failure
- **Content moderation**: input/output safety checks (Alibaba Cloud Content Safety)
- **Rate limiting**: per-API-key sliding window
- **Usage logging**: per-call analytics with latency and credit consumption

## Quick Start

### Remote (Streamable HTTP)

Add to your MCP client config (Claude Desktop, Cursor, etc.):

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

### Local (stdio)

```bash
pip install searchpipe-mcp
export SEARCHPIPE_API_KEY=sp-your-api-key-here
searchpipe-mcp
```

Or with `uvx`:

```bash
uvx searchpipe-mcp
```

## Getting an API Key

1. Sign up at [searchpipe.tech](https://searchpipe.tech)
2. Verify your email
3. Go to Dashboard → API Keys → copy your `sp-` key
4. New accounts receive free credits to try the service

## Tool Schema

### `searchpipe_search`

Run an AI-powered web search.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | ✅ | — | Search query |
| `max_results` | integer | — | 5 | Number of results (1–20) |
| `include_answer` | boolean | — | false | Include AI-generated answer |
| `include_raw_content` | boolean | — | false | Include full page content |
| `api_key` | string | — | — | API key (or use env var / URL param) |

**Returns**: Tavily-style `SearchResponse` with `query`, `answer`, `results[]`.

## Self-Hosting

SearchPipe is open-source and self-hostable. The full server (FastAPI + SearXNG + PostgreSQL + Redis) is available at [github.com/engineer566/searchpipe](https://github.com/engineer566/searchpipe).

## Links

- **Website**: [searchpipe.tech](https://searchpipe.tech)
- **API Docs**: [searchpipe.tech/docs](https://searchpipe.tech/docs)
- **MCP Endpoint**: `https://searchpipe.tech/mcp/`
- **Full Server Source**: [github.com/engineer566/searchpipe](https://github.com/engineer566/searchpipe)

## License

MIT
