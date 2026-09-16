# langchain-searchpipe

[![PyPI](https://img.shields.io/pypi/v/langchain-searchpipe)](https://pypi.org/project/langchain-searchpipe/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![SearchPipe](https://img.shields.io/badge/Powered%20by-SearchPipe-green)](https://searchpipe.tech)

LangChain integration for [SearchPipe](https://searchpipe.tech) — an AI-powered web search API (Tavily-style) that aggregates SearXNG multi-engine retrieval, trafilatura content extraction, and LLM reranking/summarization into a single `/search` endpoint.

## Installation

```bash
pip install langchain-searchpipe
```

## Getting an API Key

1. Sign up at [searchpipe.tech](https://searchpipe.tech)
2. Verify your email
3. Dashboard → API Keys → copy your `sp-` key
4. New accounts receive free credits to try the service

Set the key as an environment variable (recommended):

```bash
export SEARCHPIPE_API_KEY=sp-your-api-key-here
```

Or pass it explicitly to each component via `api_key=`.

## Usage

### Retriever (RAG pipelines)

```python
from langchain_searchpipe import SearchPipeRetriever

retriever = SearchPipeRetriever(
    max_results=5,
    search_depth="basic",          # "basic" = 1 credit, "advanced" = 2 credits
    include_raw_content=False,     # True fetches full page content (slower)
)

docs = retriever.invoke("What is the latest on fusion energy?")
for d in docs:
    print(d.metadata["url"], d.page_content[:120])
```

The retriever returns standard LangChain `Document` objects with `title`, `url`, `score`, and `query` in metadata — drop it into any existing chain that accepts a retriever.

### Tool (agents)

```python
from langchain_searchpipe import SearchPipeSearchResults, SearchPipeAnswer

# Returns structured results (title/url/content/score) — good for citation-aware agents
search_tool = SearchPipeSearchResults(max_results=5, include_answer=True)

# Returns a concise LLM-synthesized answer — good for direct Q&A agents
answer_tool = SearchPipeAnswer()

result = search_tool.invoke({"query": "current LLM agent frameworks"})
print(result["answer"])
for r in result["results"]:
    print("-", r["title"], r["url"])
```

### Self-Hosting

SearchPipe is open-source and self-hostable. To point the integration at your own instance:

```python
retriever = SearchPipeRetriever(base_url="https://your-searchpipe.example.com")
```

Full server source: [github.com/engineer566/searchpipe](https://github.com/engineer566/searchpipe).

## Features

- **Drop-in retriever** — compatible with any LangChain chain that accepts a `BaseRetriever`
- **Two tool flavors** — structured results (`SearchPipeSearchResults`) or synthesized answer (`SearchPipeAnswer`)
- **Sync + async** — all components implement both `_run`/`_arun`
- **Tavily-style response** — `query`, `answer`, `results[]` with `title`/`url`/`content`/`score`
- **Credit-based billing** — per-call credit deduction with automatic refund on failure
- **Content moderation** — input/output safety checks (Alibaba Cloud Content Safety)
- **Rate limiting** — per-API-key sliding window

## Links

- **Website**: [searchpipe.tech](https://searchpipe.tech)
- **API Docs**: [searchpipe.tech/docs](https://searchpipe.tech/docs)
- **MCP Endpoint**: `https://searchpipe.tech/mcp/`
- **Full Server Source**: [github.com/engineer566/searchpipe](https://github.com/engineer566/searchpipe)

## License

MIT
