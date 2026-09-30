/**
 * Request/response types for the SearchPipe web search API.
 *
 * The wire format mirrors the server's `/search` schema (snake_case), which is
 * the same contract the REST API and the Python SDK expose; response fields
 * are therefore deliberately **not** camelCased.
 */

import { SearchPipeError, parseNumber } from "./errors.js";

/** Wire-format request body for `POST /search` (server snake_case schema). */
export interface SearchRequest {
  query: string;
  max_results?: number;
  search_depth?: string;
  include_answer?: boolean;
  include_raw_content?: boolean;
}

/** Parameters accepted by {@link SearchPipe.search} (camelCase; converted to the snake_case body). */
export interface SearchParams {
  /** The search query. */
  query: string;
  /** Maximum number of results (server accepts 1-20, default 5). */
  maxResults?: number;
  /** `"basic"` (1 credit) or `"advanced"` (2 credits). Default `"basic"`. */
  searchDepth?: string;
  /** Generate an LLM answer with citations. Default `false`. */
  includeAnswer?: boolean;
  /** Include full fetched page content. Default `false`. */
  includeRawContent?: boolean;
  /** Per-request timeout override in milliseconds. */
  timeoutMs?: number;
}

/** A single ranked result. */
export interface SearchResult {
  url: string;
  title: string;
  /** Content snippet. */
  content: string;
  /** LLM relevance score, 0-1. */
  score: number;
  /** Full page content (set when `include_raw_content=True`). */
  raw_content: string | null;
}

/** Response of `POST /search` (snake_case, identical to the REST API). */
export interface SearchResponse {
  query: string;
  /** LLM-generated answer with citations (when `include_answer=true`). */
  answer: string | null;
  results: SearchResult[];
  /** Whether the response contains LLM-generated content. */
  ai_generated: boolean;
}

function asText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function parseSearchResult(entry: unknown): SearchResult {
  if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
    return { url: "", title: "", content: "", score: 0, raw_content: null };
  }
  const d = entry as Record<string, unknown>;
  const score = parseNumber(d["score"]) ?? 0;
  return {
    url: asText(d["url"]),
    title: asText(d["title"]),
    content: asText(d["content"]),
    score: Number.isFinite(score) ? score : 0,
    raw_content: d["raw_content"] === null || d["raw_content"] === undefined ? null : String(d["raw_content"]),
  };
}

/**
 * Build a typed {@link SearchResponse} from raw JSON, tolerating missing
 * fields so minor server additions never break older SDKs.
 */
export function parseSearchResponse(data: unknown): SearchResponse {
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new SearchPipeError("SearchPipe returned an unexpected response format.");
  }
  const d = data as Record<string, unknown>;
  const resultsRaw = Array.isArray(d["results"]) ? d["results"] : [];
  return {
    query: asText(d["query"]),
    answer: d["answer"] === null || d["answer"] === undefined ? null : String(d["answer"]),
    results: resultsRaw.map(parseSearchResult),
    ai_generated: Boolean(d["ai_generated"]),
  };
}
