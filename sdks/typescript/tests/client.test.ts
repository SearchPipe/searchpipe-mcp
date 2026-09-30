/**
 * Unit tests for the SearchPipe TypeScript SDK (zero real network).
 *
 * Every request goes through an injected stub `fetch`; responses are built
 * with the platform `Response`, so header/body semantics match production.
 */

import test from "node:test";
import assert from "node:assert/strict";
import {
  APIConnectionError,
  APIStatusError,
  AuthenticationError,
  BadRequestError,
  DEFAULT_BASE_URL,
  EmailNotVerifiedError,
  InsufficientCreditsError,
  RateLimitError,
  SearchPipe,
  SearchPipeError,
  SearchPipeServerError,
  ValidationError,
  type FetchLike,
  type SearchParams,
} from "../src/index.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface CapturedRequest {
  url: string;
  init: RequestInit;
}

function jsonResponse(status: number, body: unknown, headers?: Record<string, string>): Response {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return new Response(text, { status, headers });
}

function stubFetch(
  // A static `Response` can serve exactly ONE request; tests that issue
  // multiple requests must pass a factory returning a fresh Response each time.
  handler: Response | ((request?: CapturedRequest) => Response)
): { fetch: FetchLike; requests: CapturedRequest[] } {
  const requests: CapturedRequest[] = [];
  const impl: FetchLike = async (input, init) => {
    const request: CapturedRequest = { url: String(input), init: init ?? {} };
    requests.push(request);
    return typeof handler === "function" ? handler(request) : handler;
  };
  return { fetch: impl, requests };
}

function clientWith(
  response: Response | ((request: CapturedRequest) => Response),
  options: { apiKey?: string; baseUrl?: string } = {}
): { client: SearchPipe; requests: CapturedRequest[] } {
  const { fetch, requests } = stubFetch(response);
  return { client: new SearchPipe({ apiKey: options.apiKey ?? "sp-test-key", fetch, ...options }), requests };
}

async function searchError(
  client: SearchPipe,
  params: SearchParams
): Promise<unknown> {
  try {
    await client.search(params);
  } catch (error) {
    return error;
  }
  throw new Error("expected search() to reject, but it resolved");
}

function jsonBody(request: CapturedRequest): Record<string, unknown> {
  assert.ok(typeof request.init.body === "string", "request body must be a string");
  return JSON.parse(request.init.body) as Record<string, unknown>;
}

function headersOf(request: CapturedRequest): Record<string, string> {
  assert.ok(request.init.headers, "request must carry headers");
  return request.init.headers as Record<string, string>;
}

/** Save an env var, run `fn`, restore the previous value afterwards. */
function withEnv(name: string, value: string | undefined, fn: () => void): void {
  const saved = process.env[name];
  try {
    if (value === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
    fn();
  } finally {
    if (saved === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = saved;
    }
  }
}

const FULL_PAYLOAD = {
  query: "fastapi background tasks",
  answer: "Use BackgroundTasks to run work after the response.",
  results: [
    {
      url: "https://example.com/a",
      title: "Background Tasks",
      content: "Run work after the response.",
      score: 0.92,
      raw_content: "full page text",
    },
    {
      url: "https://example.com/b",
      title: "Starlette docs",
      content: "Background tasks reference.",
      score: 0.41,
      raw_content: null,
    },
  ],
  ai_generated: true,
};

// ---------------------------------------------------------------------------
// Success mapping
// ---------------------------------------------------------------------------

test("search maps a full success payload onto the typed response", async () => {
  const { client } = clientWith(jsonResponse(200, FULL_PAYLOAD));
  const response = await client.search({ query: "fastapi background tasks" });

  assert.equal(response.query, "fastapi background tasks");
  assert.equal(response.answer, "Use BackgroundTasks to run work after the response.");
  assert.equal(response.results.length, 2);
  assert.deepEqual(response.results[0], {
    url: "https://example.com/a",
    title: "Background Tasks",
    content: "Run work after the response.",
    score: 0.92,
    raw_content: "full page text",
  });
  assert.equal(response.results[1].raw_content, null);
  assert.equal(response.ai_generated, true);
});

test("search tolerates a success payload without answer/ai_generated", async () => {
  const { client } = clientWith(
    jsonResponse(200, {
      query: "plain search",
      results: [{ url: "https://example.com/x", title: "X", content: "snippet", score: 0.3 }],
    })
  );
  const response = await client.search({ query: "plain search" });

  assert.equal(response.answer, null);
  assert.equal(response.ai_generated, false);
  assert.equal(response.results[0].raw_content, null);
});

test("search throws SearchPipeError on a non-JSON success body", async () => {
  const { client } = clientWith(jsonResponse(200, "<html>not json</html>"));
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof SearchPipeError);
  assert.match((error as Error).message, /non-JSON success response/);
});

test("search rejects a non-object JSON success body", async () => {
  const { client } = clientWith(jsonResponse(200, ["unexpected"]));
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof SearchPipeError);
  assert.match((error as Error).message, /unexpected response format/);
});

// ---------------------------------------------------------------------------
// Request mapping
// ---------------------------------------------------------------------------

test("search posts to {base}/search with a Bearer Authorization header", async () => {
  const { client, requests } = clientWith(jsonResponse(200, FULL_PAYLOAD));
  await client.search({ query: "q" });

  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, `${DEFAULT_BASE_URL}/search`);
  assert.equal(requests[0].init.method, "POST");
  const headers = headersOf(requests[0]);
  assert.equal(headers["Authorization"], "Bearer sp-test-key");
  assert.equal(headers["Content-Type"], "application/json");
});

test("search converts camelCase params to the snake_case request body", async () => {
  const { client, requests } = clientWith(jsonResponse(200, FULL_PAYLOAD));
  await client.search({
    query: "hello",
    maxResults: 10,
    searchDepth: "advanced",
    includeAnswer: true,
    includeRawContent: true,
  });

  assert.deepEqual(jsonBody(requests[0]), {
    query: "hello",
    max_results: 10,
    search_depth: "advanced",
    include_answer: true,
    include_raw_content: true,
  });
});

test("search fills the server defaults for omitted params", async () => {
  const { client, requests } = clientWith(jsonResponse(200, FULL_PAYLOAD));
  await client.search({ query: "hello" });

  assert.deepEqual(jsonBody(requests[0]), {
    query: "hello",
    max_results: 5,
    search_depth: "basic",
    include_answer: false,
    include_raw_content: false,
  });
});

test("a custom baseUrl is used and trailing slashes are stripped", async () => {
  const { client, requests } = clientWith(jsonResponse(200, FULL_PAYLOAD), {
    baseUrl: "http://127.0.0.1:8001///",
  });
  await client.search({ query: "q" });

  assert.equal(client.baseUrl, "http://127.0.0.1:8001");
  assert.equal(requests[0].url, "http://127.0.0.1:8001/search");
});

test("each request carries an abort signal driven by timeoutMs", async () => {
  const { client, requests } = clientWith(() => jsonResponse(200, FULL_PAYLOAD), { timeoutMs: 250 });
  await client.search({ query: "q" });
  assert.ok(requests[0].init.signal instanceof AbortSignal);

  await client.search({ query: "q", timeoutMs: 5000 });
  assert.ok(requests[1].init.signal instanceof AbortSignal);
});

// ---------------------------------------------------------------------------
// Error mapping
// ---------------------------------------------------------------------------

test("401 maps to AuthenticationError with the server detail", async () => {
  const { client } = clientWith(jsonResponse(401, { detail: "Invalid API key" }));
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof AuthenticationError);
  assert.ok(error instanceof APIStatusError);
  assert.ok(error instanceof SearchPipeError);
  assert.equal((error as AuthenticationError).status, 401);
  assert.equal((error as AuthenticationError).message, "Invalid API key");
});

test("403 maps to EmailNotVerifiedError", async () => {
  const { client } = clientWith(
    jsonResponse(403, { detail: "Email not verified. Please verify your email first." })
  );
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof EmailNotVerifiedError);
  assert.equal((error as EmailNotVerifiedError).status, 403);
  assert.match((error as EmailNotVerifiedError).message, /Email not verified/);
});

test("402 maps to InsufficientCreditsError with parsed balance/required", async () => {
  const { client } = clientWith(
    jsonResponse(402, {
      detail: "Insufficient credits: balance 1.5, this call requires 2",
    })
  );
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof InsufficientCreditsError);
  const credits = error as InsufficientCreditsError;
  assert.equal(credits.status, 402);
  assert.equal(credits.balance, 1.5);
  assert.equal(credits.required, 2);
});

test("429 maps to RateLimitError with retryAfter parsed from Retry-After", async () => {
  const { client } = clientWith(
    jsonResponse(429, { detail: "Rate limit exceeded" }, { "Retry-After": "30" })
  );
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof RateLimitError);
  const rateLimit = error as RateLimitError;
  assert.equal(rateLimit.status, 429);
  assert.equal(rateLimit.retryAfter, 30);
  assert.equal(rateLimit.headers["retry-after"], "30");
});

test("429 without a Retry-After header yields retryAfter = null", async () => {
  const { client } = clientWith(jsonResponse(429, { detail: "Rate limit exceeded" }));
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof RateLimitError);
  assert.equal((error as RateLimitError).retryAfter, null);
});

test("400 maps to BadRequestError (but not ValidationError)", async () => {
  const { client } = clientWith(
    jsonResponse(400, { detail: "Output content violation: ['violence']" })
  );
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof BadRequestError);
  assert.ok(!(error instanceof ValidationError));
  assert.equal((error as BadRequestError).status, 400);
});

test("422 maps to ValidationError, a subclass of BadRequestError", async () => {
  const detail = [
    {
      type: "string_too_long",
      loc: ["body", "query"],
      msg: "String should have at most 2000 characters",
    },
  ];
  const { client } = clientWith(jsonResponse(422, { detail }));
  const error = await searchError(client, { query: "x".repeat(2001) });

  assert.ok(error instanceof ValidationError);
  assert.ok(error instanceof BadRequestError);
  assert.equal((error as ValidationError).status, 422);
  assert.equal((error as ValidationError).message, JSON.stringify(detail));
});

test("502 maps to SearchPipeServerError", async () => {
  const { client } = clientWith(
    jsonResponse(502, { detail: "Search backend failure: upstream timeout" })
  );
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof SearchPipeServerError);
  assert.equal((error as SearchPipeServerError).status, 502);
});

test("other non-2xx statuses fall back to APIStatusError", async () => {
  const { client } = clientWith(jsonResponse(409, { detail: "Conflict" }));
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof APIStatusError);
  assert.ok(!(error instanceof BadRequestError));
  assert.ok(!(error instanceof SearchPipeServerError));
  assert.equal((error as APIStatusError).status, 409);
});

test("non-JSON error bodies keep the truncated body and a fallback message", async () => {
  const { client } = clientWith(
    jsonResponse(502, "<html>Bad Gateway</html>", { "content-type": "text/html" })
  );
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof SearchPipeServerError);
  const serverError = error as SearchPipeServerError;
  assert.match(serverError.message, /without an error detail/);
  assert.equal(serverError.body, "<html>Bad Gateway</html>");
});

// ---------------------------------------------------------------------------
// Connection errors
// ---------------------------------------------------------------------------

test("fetch rejections map to APIConnectionError", async () => {
  const failingFetch: FetchLike = async () => {
    throw new TypeError("fetch failed");
  };
  const client = new SearchPipe({ apiKey: "sp-test-key", fetch: failingFetch });
  const error = await searchError(client, { query: "q" });

  assert.ok(error instanceof APIConnectionError);
  assert.match((error as APIConnectionError).message, /Could not connect to SearchPipe/);
  assert.match((error as APIConnectionError).message, /fetch failed/);
});

test("a per-call timeoutMs aborts the request and maps to APIConnectionError", async () => {
  // AbortSignal.timeout timers do not keep the Node event loop alive, and the
  // stub has no pending I/O, so hold the loop open until the abort settles.
  const keepAlive = setInterval(() => {}, 10);
  const hangingFetch: FetchLike = (_input, init) =>
    new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        reject(new DOMException("The operation was aborted.", "TimeoutError"));
      });
    });
  const client = new SearchPipe({ apiKey: "sp-test-key", fetch: hangingFetch });

  try {
    await assert.rejects(client.search({ query: "q", timeoutMs: 20 }), APIConnectionError);
  } finally {
    clearInterval(keepAlive);
  }
});

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

test("a missing API key (no option, no env) raises SearchPipeError", () => {
  withEnv("SEARCHPIPE_API_KEY", undefined, () => {
    assert.throws(() => new SearchPipe({ fetch: stubFetch(jsonResponse(200, {})).fetch }), (error: unknown) => {
      assert.ok(error instanceof SearchPipeError);
      assert.match((error as SearchPipeError).message, /SEARCHPIPE_API_KEY/);
      return true;
    });
  });
});

test("SEARCHPIPE_API_KEY is used when no apiKey option is passed", async () => {
  const saved = process.env["SEARCHPIPE_API_KEY"];
  process.env["SEARCHPIPE_API_KEY"] = "sp-from-env";
  try {
    // Construct directly (no injected apiKey) so the env fallback is exercised.
    const { fetch, requests } = stubFetch(() => jsonResponse(200, FULL_PAYLOAD));
    const client = new SearchPipe({ fetch });
    await client.search({ query: "q" });
    assert.equal(headersOf(requests[0])["Authorization"], "Bearer sp-from-env");
  } finally {
    if (saved === undefined) delete process.env["SEARCHPIPE_API_KEY"];
    else process.env["SEARCHPIPE_API_KEY"] = saved;
  }
});

test("SEARCHPIPE_BASE_URL is used when no baseUrl option is passed", async () => {
  const saved = process.env["SEARCHPIPE_BASE_URL"];
  process.env["SEARCHPIPE_BASE_URL"] = "http://127.0.0.1:8001/";
  try {
    const { client, requests } = clientWith(jsonResponse(200, FULL_PAYLOAD));
    assert.equal(client.baseUrl, "http://127.0.0.1:8001");
    await client.search({ query: "q" });
    assert.equal(requests[0].url, "http://127.0.0.1:8001/search");
  } finally {
    if (saved === undefined) delete process.env["SEARCHPIPE_BASE_URL"];
    else process.env["SEARCHPIPE_BASE_URL"] = saved;
  }
});

test("close() is an idempotent no-op", () => {
  const { client } = clientWith(jsonResponse(200, FULL_PAYLOAD));
  client.close();
  client.close();
});
