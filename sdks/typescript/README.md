# SearchPipe TypeScript SDK

Official JavaScript/TypeScript SDK for the SearchPipe web search API.

SearchPipe is a web search API and MCP server for developers building AI agents. This SDK is a thin, zero-dependency client on top of the platform `fetch`, covering the full `POST /search` parameter set — ranked results, optional LLM answers with citations, and optional raw page content — for Node.js (>= 18), browsers, and edge runtimes.

## Install

```bash
npm install searchpipe
```

Requires Node 18+ (or any runtime with a global `fetch`). Zero runtime dependencies. Ships ESM and CommonJS builds with TypeScript type definitions.

## Quickstart

### ESM (import)

```js
import { SearchPipe } from "searchpipe";

const client = new SearchPipe({ apiKey: "sp-YOUR_KEY" });

const response = await client.search({
  query: "latest node release notes",
  maxResults: 5,             // 1-20
  searchDepth: "basic",      // "basic" (1 credit) or "advanced" (2 credits)
  includeAnswer: true,       // generate an LLM answer with citations
  includeRawContent: false,  // include full fetched page content
});

console.log(response.answer);
for (const result of response.results) {
  console.log(result.score, result.url, result.title);
  console.log(result.content);
  // result.raw_content is set when includeRawContent=true
}
```

### CommonJS (require)

```js
const { SearchPipe } = require("searchpipe");

async function main() {
  const client = new SearchPipe({ apiKey: "sp-YOUR_KEY" });
  const response = await client.search({
    query: "fastapi background tasks",
    includeAnswer: true,
  });
  for (const result of response.results) {
    console.log(result.url, result.title);
  }
  client.close();
}

main();
```

`close()` is a no-op kept for symmetry with the Python SDK (the platform `fetch` keeps no client-side connection pool); it is safe to call multiple times.

## API

### `client.search(params)`

Arguments are camelCase and are converted to the server's snake_case request body:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | — (required) | The search query |
| `maxResults` | `number` | `5` | Maximum number of results (server accepts 1-20) |
| `searchDepth` | `string` | `"basic"` | `"basic"` (1 credit) or `"advanced"` (2 credits) |
| `includeAnswer` | `boolean` | `false` | Generate an LLM answer with citations |
| `includeRawContent` | `boolean` | `false` | Include full fetched page content |
| `timeoutMs` | `number` | client default | Per-request timeout override |

### Response

`search()` resolves to a typed `SearchResponse` whose fields keep the server's snake_case naming (identical to the REST API and the Python SDK — response fields are deliberately **not** camelCased):

| Field | Type | Description |
|---|---|---|
| `query` | `string` | The executed query |
| `answer` | `string \| null` | LLM-generated answer with citations (when `include_answer=true`) |
| `results` | `SearchResult[]` | Ranked results: `url`, `title`, `content`, `score`, `raw_content` |
| `ai_generated` | `boolean` | Whether the response contains LLM-generated content |

## Error handling

Every non-2xx response raises a typed error from the hierarchy below:

| Error | HTTP status | Meaning |
|---|---|---|
| `AuthenticationError` | 401 | API key is missing, malformed, or revoked |
| `InsufficientCreditsError` | 402 | Not enough credits (exposes `balance` / `required` when the server reports them) |
| `EmailNotVerifiedError` | 403 | Account email has not been verified |
| `BadRequestError` | 400 | Request or generated output was rejected |
| `ValidationError` | 422 | Request validation failed (subclass of `BadRequestError`) |
| `RateLimitError` | 429 | Rate limit exceeded (exposes `retryAfter` from the `Retry-After` header, `null` if absent) |
| `SearchPipeServerError` | 5xx | Upstream/internal failure on the SearchPipe side |
| `APIStatusError` | other | Any other non-2xx status (base class of all status errors) |
| `APIConnectionError` | — | Network failure: DNS, connection refused, timeout |
| `SearchPipeError` | — | Base class of everything this SDK throws |

`APIStatusError` exposes `status`, `message`, `headers`, and a truncated raw `body`.

```js
import { SearchPipe, RateLimitError, APIConnectionError } from "searchpipe";

const client = new SearchPipe({ apiKey: "sp-YOUR_KEY" });
try {
  const response = await client.search({ query: "hello world" });
} catch (error) {
  if (error instanceof RateLimitError) {
    if (error.retryAfter) console.log(`retry in ${error.retryAfter} seconds`);
  } else if (error instanceof APIConnectionError) {
    console.log("network problem:", error.message);
  } else {
    throw error;
  }
}
```

Error messages prefer the API's `detail` field; non-JSON error bodies never crash the SDK (the truncated body is kept on `error.body`).

## Configuration

| Option | Environment variable | Default |
|---|---|---|
| `apiKey` | `SEARCHPIPE_API_KEY` | — (required; throws `SearchPipeError` if neither is set) |
| `baseUrl` | `SEARCHPIPE_BASE_URL` | `https://searchpipe.tech` |
| `timeoutMs` | — | `60000` milliseconds |
| `fetch` | — | the global `fetch` (inject for tests or non-global runtimes) |

Point `baseUrl` at a self-hosted SearchPipe instance:

```js
const client = new SearchPipe({
  apiKey: "sp-YOUR_KEY",
  baseUrl: "https://your-instance.example.com",
});
```

Trailing slashes on `baseUrl` are stripped automatically. `search()` also accepts a per-call `timeoutMs` override.
