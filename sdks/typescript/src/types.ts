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

/** Verbatim evidence attached to a search result (when evidence is enabled). */
export interface ResultEvidence {
  /** Supporting sentence quoted verbatim from the fetched page. */
  quote: string;
  /** Quote start offset (into raw_content, or content when snippet-fallback). */
  span_start: number | null;
  /** Quote end offset (exclusive). */
  span_end: number | null;
  /** Source authority tier: official/press/academic/preprint/community/unknown. */
  source_tier: string;
  /** HTTP status of the page fetch (null = not fetched/timeout). */
  fetch_status: number | null;
  /** Whether the fetch followed redirects. */
  redirected: boolean;
  /** Final URL after redirects. */
  final_url: string | null;
  /** Fetch completion time, ISO-8601 UTC. */
  fetched_at: string | null;
}

/** The cited result backing one audited statement. */
export interface StatementCitation {
  url: string;
  title: string | null;
  /** Supporting span quoted from the cited page (null = no page text). */
  quote: string | null;
  span_start: number | null;
  span_end: number | null;
}

/** Per-statement audit of an AI answer. */
export interface StatementAudit {
  /** Answer statement (citation markers stripped). */
  text: string;
  /** supported/partial/unsupported/inconclusive (judged) or uncited (not judged). */
  verdict: string;
  /** Judge confidence 0-1 (0 for uncited). */
  confidence: number;
  citations: StatementCitation[];
}

/** Per-statement audit of the AI answer (advanced depth only). */
export interface AnswerAudit {
  /** Fraction of judged statements that are supported, 0-1. */
  score: number;
  /** Statements without any [n] citation marker. */
  uncited_count: number;
  statements: StatementAudit[];
  /** Audit judge prompt version. */
  prompt_version: string;
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
  /** Verbatim evidence: quote, span, source tier and fetch metadata (when enabled). */
  evidence: ResultEvidence | null;
}

/** Response of `POST /search` (snake_case, identical to the REST API). */
export interface SearchResponse {
  query: string;
  /** LLM-generated answer with citations (when `include_answer=true`). */
  answer: string | null;
  results: SearchResult[];
  /** Whether the response contains LLM-generated content. */
  ai_generated: boolean;
  /** Per-statement audit of the AI answer (advanced depth, when enabled). */
  answer_audit: AnswerAudit | null;
}

function asText(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function parseSearchResult(entry: unknown): SearchResult {
  if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
    return { url: "", title: "", content: "", score: 0, raw_content: null, evidence: null };
  }
  const d = entry as Record<string, unknown>;
  const score = parseNumber(d["score"]) ?? 0;
  const evRaw = d["evidence"];
  let evidence: ResultEvidence | null = null;
  if (evRaw !== null && evRaw !== undefined && typeof evRaw === "object" && !Array.isArray(evRaw)) {
    const ev = evRaw as Record<string, unknown>;
    evidence = {
      quote: asText(ev["quote"]),
      span_start: parseNumber(ev["span_start"]),
      span_end: parseNumber(ev["span_end"]),
      source_tier: asText(ev["source_tier"]) || "unknown",
      fetch_status: parseNumber(ev["fetch_status"]),
      redirected: Boolean(ev["redirected"]),
      final_url: ev["final_url"] === null || ev["final_url"] === undefined ? null : String(ev["final_url"]),
      fetched_at: ev["fetched_at"] === null || ev["fetched_at"] === undefined ? null : String(ev["fetched_at"]),
    };
  }
  return {
    url: asText(d["url"]),
    title: asText(d["title"]),
    content: asText(d["content"]),
    score: Number.isFinite(score) ? score : 0,
    raw_content: d["raw_content"] === null || d["raw_content"] === undefined ? null : String(d["raw_content"]),
    evidence,
  };
}

function parseStatementCitation(entry: unknown): StatementCitation {
  if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
    return { url: "", title: null, quote: null, span_start: null, span_end: null };
  }
  const d = entry as Record<string, unknown>;
  return {
    url: asText(d["url"]),
    title: d["title"] === null || d["title"] === undefined ? null : String(d["title"]),
    quote: d["quote"] === null || d["quote"] === undefined ? null : String(d["quote"]),
    span_start: parseNumber(d["span_start"]),
    span_end: parseNumber(d["span_end"]),
  };
}

function parseStatementAudit(entry: unknown): StatementAudit {
  if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
    return { text: "", verdict: "", confidence: 0, citations: [] };
  }
  const d = entry as Record<string, unknown>;
  const confidence = parseNumber(d["confidence"]) ?? 0;
  const citationsRaw = Array.isArray(d["citations"]) ? d["citations"] : [];
  return {
    text: asText(d["text"]),
    verdict: asText(d["verdict"]),
    confidence: Number.isFinite(confidence) ? confidence : 0,
    citations: citationsRaw.map(parseStatementCitation),
  };
}

function parseAnswerAudit(entry: unknown): AnswerAudit | null {
  if (entry === null || entry === undefined || typeof entry !== "object" || Array.isArray(entry)) {
    return null;
  }
  const d = entry as Record<string, unknown>;
  const score = parseNumber(d["score"]) ?? 0;
  const uncited = parseNumber(d["uncited_count"]) ?? 0;
  const statementsRaw = Array.isArray(d["statements"]) ? d["statements"] : [];
  return {
    score: Number.isFinite(score) ? score : 0,
    uncited_count: Number.isFinite(uncited) ? uncited : 0,
    statements: statementsRaw.map(parseStatementAudit),
    prompt_version: asText(d["prompt_version"]),
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
    answer_audit: parseAnswerAudit(d["answer_audit"]),
  };
}

// ---------------------------------------------------------------------------
// Verify (POST /verify) — claim in, verdict out
// ---------------------------------------------------------------------------

/** Wire-format request body for `POST /verify` (server snake_case schema). */
export interface VerifyRequest {
  claim: string;
  mode?: string;
  evidence_urls?: string[];
  max_evidence?: number;
}

/** Parameters accepted by {@link SearchPipe.verify} (camelCase; converted to the snake_case body). */
export interface VerifyParams {
  /** The claim (statement or query) to verify. */
  claim: string;
  /** Evidence route: `"paper"`, `"web"`, or `"auto"` (default; a DOI or arXiv signal decides). */
  mode?: string;
  /** Up to 5 caller-supplied citations to verify. */
  evidenceUrls?: string[];
  /** Maximum evidence items to return (1-10, server default 5). */
  maxEvidence?: number;
  /** Per-request timeout override in milliseconds. Verification typically takes 5-15s. */
  timeoutMs?: number;
}

/** URL health info for one evidence item. */
export interface UrlHealth {
  status_code: number | null;
  redirected: boolean;
  wayback_snapshot: boolean | null;
  fetched_at: string | null;
}

/** A single piece of evidence backing the verdict (span-level quote from the source text). */
export interface VerifyEvidence {
  url: string;
  title: string | null;
  source_tier: string;
  quote: string | null;
  span_start: number | null;
  span_end: number | null;
  per_evidence_verdict: string | null;
  confidence: number | null;
  url_health: UrlHealth | null;
}

/**
 * Response of `POST /verify` (snake_case, identical to the REST API).
 *
 * `verdict` is one of `supported` / `partial` / `unsupported` / `inconclusive`;
 * `inconclusive` means the claim could not be judged (fetch failure, paywall,
 * or insufficient evidence) — the API reports that instead of guessing.
 */
export interface VerifyResponse {
  verdict: string;
  confidence: number;
  reason_code: string;
  evidences: VerifyEvidence[];
  /** Per-stage wall time in seconds. */
  timing: Record<string, number>;
}

function optText(value: unknown): string | null {
  return value === null || value === undefined ? null : String(value);
}

function optNumber(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  return parseNumber(value);
}

function parseUrlHealth(value: unknown): UrlHealth | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  const d = value as Record<string, unknown>;
  return {
    status_code: optNumber(d["status_code"]),
    redirected: Boolean(d["redirected"]),
    wayback_snapshot:
      d["wayback_snapshot"] === null || d["wayback_snapshot"] === undefined
        ? null
        : Boolean(d["wayback_snapshot"]),
    fetched_at: optText(d["fetched_at"]),
  };
}

function parseVerifyEvidence(entry: unknown): VerifyEvidence {
  if (entry === null || typeof entry !== "object" || Array.isArray(entry)) {
    return {
      url: "",
      title: null,
      source_tier: "unknown",
      quote: null,
      span_start: null,
      span_end: null,
      per_evidence_verdict: null,
      confidence: null,
      url_health: null,
    };
  }
  const d = entry as Record<string, unknown>;
  return {
    url: asText(d["url"]),
    title: optText(d["title"]),
    source_tier: d["source_tier"] === null || d["source_tier"] === undefined ? "unknown" : String(d["source_tier"]),
    quote: optText(d["quote"]),
    span_start: optNumber(d["span_start"]),
    span_end: optNumber(d["span_end"]),
    per_evidence_verdict: optText(d["per_evidence_verdict"]),
    confidence: optNumber(d["confidence"]),
    url_health: parseUrlHealth(d["url_health"]),
  };
}

/**
 * Build a typed {@link VerifyResponse} from raw JSON, tolerating missing
 * fields so minor server additions never break older SDKs.
 */
export function parseVerifyResponse(data: unknown): VerifyResponse {
  if (data === null || typeof data !== "object" || Array.isArray(data)) {
    throw new SearchPipeError("SearchPipe returned an unexpected response format.");
  }
  const d = data as Record<string, unknown>;
  const evidencesRaw = Array.isArray(d["evidences"]) ? d["evidences"] : [];
  const timing: Record<string, number> = {};
  if (d["timing"] !== null && typeof d["timing"] === "object" && !Array.isArray(d["timing"])) {
    for (const [key, value] of Object.entries(d["timing"] as Record<string, unknown>)) {
      const parsed = parseNumber(value);
      if (parsed !== null) timing[key] = parsed;
    }
  }
  return {
    verdict: asText(d["verdict"]),
    confidence: optNumber(d["confidence"]) ?? 0,
    reason_code: asText(d["reason_code"]),
    evidences: evidencesRaw.map(parseVerifyEvidence),
    timing,
  };
}
