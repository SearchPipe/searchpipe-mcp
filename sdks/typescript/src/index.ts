/**
 * Official JavaScript/TypeScript SDK for the SearchPipe web search API.
 *
 * SearchPipe is a web search API and MCP server for developers building AI
 * agents. This SDK is a thin, zero-dependency fetch client covering the full
 * `POST /search` parameter set — ranked results, optional LLM answers with
 * citations, and optional raw page content.
 *
 * @example
 * ```ts
 * import { SearchPipe } from "searchpipe";
 *
 * const client = new SearchPipe({ apiKey: "sp-YOUR_KEY" });
 * const response = await client.search({ query: "hello world", includeAnswer: true });
 * ```
 */

export {
  SearchPipe,
  DEFAULT_BASE_URL,
  ENV_API_KEY,
  ENV_BASE_URL,
} from "./client.js";
export type { FetchLike, SearchPipeOptions } from "./client.js";

export {
  APIConnectionError,
  APIStatusError,
  AuthenticationError,
  BadRequestError,
  EmailNotVerifiedError,
  InsufficientCreditsError,
  RateLimitError,
  SearchPipeError,
  SearchPipeServerError,
  ValidationError,
} from "./errors.js";
export type { APIStatusErrorOptions, HeadersLike } from "./errors.js";

export type {
  SearchParams,
  SearchRequest,
  SearchResponse,
  SearchResult,
} from "./types.js";
