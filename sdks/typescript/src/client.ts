/**
 * Thin fetch-based client for the SearchPipe web search API.
 *
 * Zero runtime dependencies: uses the platform `fetch` (Node >= 18, browsers
 * and edge runtimes). Non-2xx responses are mapped onto the typed error
 * hierarchy in {@link ./errors.ts}.
 */

import { APIConnectionError, SearchPipeError, errorFromResponse } from "./errors.js";
import {
  parseSearchResponse,
  type SearchParams,
  type SearchRequest,
  type SearchResponse,
} from "./types.js";

export const DEFAULT_BASE_URL = "https://searchpipe.tech";
export const ENV_API_KEY = "SEARCHPIPE_API_KEY";
export const ENV_BASE_URL = "SEARCHPIPE_BASE_URL";

const DEFAULT_TIMEOUT_MS = 60_000;

/** A `fetch`-compatible function; defaults to the global `fetch`. */
export type FetchLike = typeof fetch;

export interface SearchPipeOptions {
  /**
   * API key (`sp-...`). Falls back to the `SEARCHPIPE_API_KEY` environment
   * variable; raises {@link SearchPipeError} when neither is set.
   */
  apiKey?: string;
  /**
   * API base URL. Falls back to `SEARCHPIPE_BASE_URL`, then to
   * `https://searchpipe.tech`. Override it to target a self-hosted instance.
   * Trailing slashes are stripped.
   */
  baseUrl?: string;
  /** Custom `fetch` implementation (for tests or non-global runtimes). */
  fetch?: FetchLike;
  /** Default request timeout in milliseconds. Default `60000`. */
  timeoutMs?: number;
}

function envValue(name: string): string | undefined {
  if (typeof process === "undefined" || !process.env) return undefined;
  return process.env[name];
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}

async function safeText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return "";
  }
}

export class SearchPipe {
  private readonly apiKey: string;
  private readonly _baseUrl: string;
  private readonly fetchImpl: FetchLike;
  private readonly timeoutMs: number;

  constructor(options: SearchPipeOptions = {}) {
    let apiKey = options.apiKey ?? envValue(ENV_API_KEY);
    if (!apiKey) {
      throw new SearchPipeError(
        "Missing API key: pass apiKey=... or set the SEARCHPIPE_API_KEY " +
          "environment variable. Get a key at https://searchpipe.tech"
      );
    }
    const baseUrl = options.baseUrl ?? envValue(ENV_BASE_URL) ?? DEFAULT_BASE_URL;

    this.apiKey = apiKey;
    this._baseUrl = baseUrl.replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

    const fetchImpl = options.fetch ?? globalThis.fetch;
    if (typeof fetchImpl !== "function") {
      throw new SearchPipeError(
        "This environment does not provide a global `fetch` (Node >= 18 required). " +
          "Pass a custom `fetch` implementation via the constructor options."
      );
    }
    this.fetchImpl = fetchImpl;
  }

  /** Effective base URL (trailing slash stripped). */
  get baseUrl(): string {
    return this._baseUrl;
  }

  /**
   * Run a web search via `POST /search`.
   *
   * @returns A typed {@link SearchResponse} (snake_case fields, as served by
   *   the REST API and consumed by the Python SDK).
   * @throws {SearchPipeError} Typed subclasses per the error contract — see
   *   {@link ./errors.ts}.
   */
  async search(params: SearchParams): Promise<SearchResponse> {
    // Mirror the server's snake_case schema, filling the same defaults as the
    // Python SDK so both clients always send the full parameter set.
    const body: SearchRequest = {
      query: params.query,
      max_results: params.maxResults ?? 5,
      search_depth: params.searchDepth ?? "basic",
      include_answer: params.includeAnswer ?? false,
      include_raw_content: params.includeRawContent ?? false,
    };

    const init: RequestInit = {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(params.timeoutMs ?? this.timeoutMs),
    };

    let response: Response;
    try {
      response = await this.fetchImpl(`${this._baseUrl}/search`, init);
    } catch (error) {
      throw new APIConnectionError(
        `Could not connect to SearchPipe at ${this._baseUrl}: ${errorMessage(error)}`
      );
    }
    return this.processResponse(response);
  }

  private async processResponse(response: Response): Promise<SearchResponse> {
    const text = await safeText(response);
    if (!response.ok) {
      throw errorFromResponse(response.status, response.headers, text);
    }
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      throw new SearchPipeError(
        `SearchPipe returned a non-JSON success response (HTTP ${response.status}).`
      );
    }
    return parseSearchResponse(data);
  }

  /**
   * Release the underlying HTTP resources.
   *
   * The SDK uses the platform `fetch`, which keeps no client-side connection
   * pool, so this is a no-op kept for API symmetry with the Python SDK.
   * Idempotent: safe to call more than once.
   */
  close(): void {
    // No-op by design — see the doc comment above.
  }
}
