# SearchPipe Python SDK

Official Python SDK for the SearchPipe web search API — verifiable evidence with every result.

SearchPipe is a web search API and MCP server for developers building AI agents. This SDK is a thin httpx-based client covering the full `POST /search` parameter set — ranked results, optional LLM answers with citations, and optional raw page content — in both synchronous and asynchronous flavors.

## Install

```bash
pip install searchpipe
```

Requires Python 3.9+. The only runtime dependency is `httpx`.

## Quickstart

### Synchronous

```python
from searchpipe import SearchPipe

client = SearchPipe(api_key="sp-YOUR_KEY")

response = client.search(
    "latest python release notes",
    max_results=5,            # 1-20
    search_depth="basic",     # "basic" (1 credit) or "advanced" (2 credits)
    include_answer=True,      # generate an LLM answer with citations
    include_raw_content=False # include full fetched page content
)

print(response.answer)
for result in response.results:
    print(result.score, result.url, result.title)
    print(result.content)
    # result.raw_content is set when include_raw_content=True
```

### Asynchronous

```python
import asyncio
from searchpipe import AsyncSearchPipe

async def main():
    async with AsyncSearchPipe(api_key="sp-YOUR_KEY") as client:
        response = await client.search(
            "fastapi background tasks",
            include_answer=True,
        )
        for result in response.results:
            print(result.url, result.title)

asyncio.run(main())
```

Both clients support `close()` and context managers (`with` / `async with`).

### Verify a claim

```python
result = client.verify(
    "The transformer paper introduced self-attention in 2017",
    mode="auto",        # "paper" / "web" / "auto" (DOI or arXiv signal decides)
    max_evidence=5,     # 1-10
)

print(result.verdict)       # supported / partial / unsupported / inconclusive
print(result.confidence, result.reason_code)
for evidence in result.evidences:
    print(evidence.source_tier, evidence.url)
    print(evidence.quote)   # span-level quote from the source text
```

`verify()` returns a `VerifyResponse` dataclass:

| Field | Type | Description |
|---|---|---|
| `verdict` | `str` | `supported` / `partial` / `unsupported` / `inconclusive` |
| `confidence` | `float` | 0-1 |
| `reason_code` | `str` | Machine-readable template phrase (e.g. `quote_span_found`, `paywall`) |
| `evidences` | `list[VerifyEvidence]` | `url`, `title`, `source_tier`, `quote`, `span_start`/`span_end`, `per_evidence_verdict`, `confidence`, `url_health` |
| `timing` | `dict[str, float]` | Per-stage wall time in seconds |

`inconclusive` is a first-class outcome (fetch failure, paywall, or insufficient evidence) — the API reports that instead of guessing. Verification fetches source pages, so expect **5–15 seconds** per call. Credits are charged per request; `inconclusive` is a delivered result and is not refunded, while failed calls are refunded automatically.

## Responses

`client.search()` returns a `SearchResponse` dataclass:

| Field | Type | Description |
|---|---|---|
| `query` | `str` | The executed query |
| `answer` | `str \| None` | LLM-generated answer with citations (when `include_answer=True`) |
| `results` | `list[SearchResult]` | Ranked results: `url`, `title`, `content`, `score`, `raw_content` |
| `ai_generated` | `bool` | Whether the response contains LLM-generated content |

## Error handling

Every non-2xx response raises a typed exception from `searchpipe.exceptions`:

| Exception | HTTP status | Meaning |
|---|---|---|
| `AuthenticationError` | 401 | API key is missing, malformed, or revoked |
| `InsufficientCreditsError` | 402 | Not enough credits (exposes `balance` / `required` when the server reports them) |
| `EmailNotVerifiedError` | 403 | Account email has not been verified |
| `BadRequestError` | 400 | Request or generated output was rejected |
| `ValidationError` | 422 | Request validation failed (subclass of `BadRequestError`) |
| `RateLimitError` | 429 | Rate limit exceeded (exposes `retry_after` from the `Retry-After` header, `None` if absent) |
| `SearchPipeServerError` | 5xx | Upstream/internal failure on the SearchPipe side |
| `APIStatusError` | other | Any other non-2xx status (base class of all status errors) |
| `APIConnectionError` | — | Network failure: DNS, connection refused, timeout |
| `SearchPipeError` | — | Base class of everything this SDK raises |

```python
from searchpipe import SearchPipe, RateLimitError, APIConnectionError

client = SearchPipe(api_key="sp-YOUR_KEY")
try:
    response = client.search("hello world")
except RateLimitError as e:
    if e.retry_after:
        print(f"retry in {e.retry_after} seconds")
except APIConnectionError as e:
    print("network problem:", e)
```

Error messages prefer the API's `detail` field; non-JSON error bodies never crash the SDK (the truncated body is kept on `e.body`).

## Configuration

| Argument | Environment variable | Default |
|---|---|---|
| `api_key` | `SEARCHPIPE_API_KEY` | — (required; raises `SearchPipeError` if neither is set) |
| `base_url` | `SEARCHPIPE_BASE_URL` | `https://searchpipe.tech` |
| `timeout` | — | `60.0` seconds |

Point `base_url` at a self-hosted SearchPipe instance:

```python
client = SearchPipe(
    api_key="sp-YOUR_KEY",
    base_url="https://your-instance.example.com",
)
```

`search()` also accepts a per-call `timeout=` override (`None` uses the client default).

> Note: the `transport=` constructor parameter exists **for tests only** (inject
> `httpx.MockTransport`); never use it in application code.
