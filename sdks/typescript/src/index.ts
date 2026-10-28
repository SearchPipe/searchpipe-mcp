/**
 * Official JavaScript/TypeScript SDK for the SearchPipe web search API.
 *
 * SearchPipe is a web search API and MCP server for developers building AI
 * agents. This SDK is a thin, zero-dependency fetch client covering `POST
 * /search` (ranked results, optional LLM answers with citations, optional raw
 * page content) and `POST /verify` (four-label claim verdicts with span-level
 * evidence quotes).
 *
 * @example
 * ```ts
 * import { SearchPipe } from "searchpipe";
 *
 * const client = new SearchPipe({ apiKey: "sp-YOUR_KEY" });
 * const response = await client.search({ query: "hello world", includeAnswer: true });
 * const verdict = await client.verify({ claim: "The Eiffel Tower opened in 1889" });
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
  AnswerAudit,
  ResultEvidence,
  SearchParams,
  SearchRequest,
  SearchResponse,
  SearchResult,
  StatementAudit,
  StatementCitation,
  UrlHealth,
  VerifyEvidence,
  VerifyParams,
  VerifyRequest,
  VerifyResponse,
} from "./types.js";
