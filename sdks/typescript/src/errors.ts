/**
 * Error hierarchy mapping the SearchPipe web search API error contract.
 *
 * Every non-2xx `/search` response is mapped to a typed error:
 *
 * - `401`    -> {@link AuthenticationError}
 * - `402`    -> {@link InsufficientCreditsError}
 * - `403`    -> {@link EmailNotVerifiedError}
 * - `422`    -> {@link ValidationError} (subclass of {@link BadRequestError})
 * - `429`    -> {@link RateLimitError} (with `retryAfter` from the `Retry-After` header)
 * - `400`    -> {@link BadRequestError}
 * - `>=500`  -> {@link SearchPipeServerError}
 * - other    -> {@link APIStatusError}
 *
 * Network-level failures (DNS, refused connection, timeouts) raise
 * {@link APIConnectionError}.
 *
 * Error messages prefer the JSON body's `detail` field; non-JSON bodies are
 * tolerated (the truncated raw body is kept on `error.body`).
 */

/** Plain-object snapshot of response headers (lower-cased keys, as fetch reports them). */
export type HeadersLike = Record<string, string>;

/** Base class for every error raised by this SDK. */
export class SearchPipeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SearchPipeError";
  }
}

/** Network failure: DNS error, connection refused/reset, or timeout. */
export class APIConnectionError extends SearchPipeError {
  constructor(message: string) {
    super(message);
    this.name = "APIConnectionError";
  }
}

/** Shared construction options for every non-2xx status error. */
export interface APIStatusErrorOptions {
  status: number;
  headers?: HeadersLike;
  body?: string | null;
}

/** The API returned a non-2xx HTTP status. */
export class APIStatusError extends SearchPipeError {
  /** HTTP status code of the response. */
  readonly status: number;
  /** Response headers, useful for e.g. rate limits. */
  readonly headers: HeadersLike;
  /** Readable summary of the raw response body (truncated), or `null`. */
  readonly body: string | null;

  constructor(message: string, options: APIStatusErrorOptions) {
    super(message);
    this.name = "APIStatusError";
    this.status = options.status;
    this.headers = options.headers ?? {};
    this.body = options.body ?? null;
  }
}

/** HTTP 401: the API key is missing, malformed, or revoked. */
export class AuthenticationError extends APIStatusError {
  constructor(message: string, options: APIStatusErrorOptions) {
    super(message, options);
    this.name = "AuthenticationError";
  }
}

/** HTTP 403: the account's email address has not been verified yet. */
export class EmailNotVerifiedError extends APIStatusError {
  constructor(message: string, options: APIStatusErrorOptions) {
    super(message, options);
    this.name = "EmailNotVerifiedError";
  }
}

/** HTTP 402: the account does not have enough credits for this call. */
export class InsufficientCreditsError extends APIStatusError {
  /** Remaining credit balance, parsed from the error detail when available. */
  readonly balance: number | null;
  /** Credits required by the call, parsed from the error detail when available. */
  readonly required: number | null;

  constructor(
    message: string,
    options: APIStatusErrorOptions & { balance?: number | null; required?: number | null }
  ) {
    super(message, options);
    this.name = "InsufficientCreditsError";
    this.balance = options.balance ?? null;
    this.required = options.required ?? null;
  }
}

/** HTTP 429: request rate limit exceeded. */
export class RateLimitError extends APIStatusError {
  /**
   * `Retry-After` response header: seconds as a `number` when parseable,
   * otherwise the raw header string; `null` when the server did not send it.
   */
  readonly retryAfter: number | string | null;

  constructor(
    message: string,
    options: APIStatusErrorOptions & { retryAfter?: number | string | null }
  ) {
    super(message, options);
    this.name = "RateLimitError";
    this.retryAfter = options.retryAfter ?? null;
  }
}

/** HTTP 400: the request (or the generated output) was rejected. */
export class BadRequestError extends APIStatusError {
  constructor(message: string, options: APIStatusErrorOptions) {
    super(message, options);
    this.name = "BadRequestError";
  }
}

/**
 * HTTP 422: request validation failed (FastAPI/pydantic contract).
 *
 * Deliberately a subclass of {@link BadRequestError}: catching
 * `BadRequestError` also catches validation failures, while this class lets
 * 422 be handled specifically.
 */
export class ValidationError extends BadRequestError {
  constructor(message: string, options: APIStatusErrorOptions) {
    super(message, options);
    this.name = "ValidationError";
  }
}

/** HTTP 5xx: an upstream/internal failure on the SearchPipe side. */
export class SearchPipeServerError extends APIStatusError {
  constructor(message: string, options: APIStatusErrorOptions) {
    super(message, options);
    this.name = "SearchPipeServerError";
  }
}

const BODY_SUMMARY_LIMIT = 500;
const BALANCE_RE = /balance\s+([0-9]+(?:\.[0-9]+)?)/i;
const REQUIRED_RE = /requires\s+([0-9]+(?:\.[0-9]+)?)/i;

/** @internal Best-effort conversion to `number`; `null` when not numeric. */
export function parseNumber(value: unknown): number | null {
  if (typeof value === "boolean") return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "string") {
    const text = value.trim();
    if (text === "") return null;
    const parsed = Number(text);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
}

function headersToRecord(headers: Headers | HeadersLike | undefined): HeadersLike {
  if (!headers) return {};
  // Duck-type fetch `Headers` (has `.entries()`) vs. plain header objects.
  const candidate = headers as unknown as Partial<Headers>;
  if (typeof candidate.entries === "function") {
    return Object.fromEntries(candidate.entries());
  }
  return { ...(headers as HeadersLike) };
}

function parseRetryAfter(headers: HeadersLike): number | string | null {
  const raw = headers["retry-after"];
  if (raw === undefined || raw === null) return null;
  const text = String(raw).trim();
  if (/^\d+$/.test(text)) return Number.parseInt(text, 10);
  return text;
}

function messageFor(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.length > 0) return detail;
  if (detail !== null && typeof detail === "object") {
    const json = JSON.stringify(detail);
    if (json !== undefined && json !== "{}" && json !== "[]") return json;
  }
  return `SearchPipe API returned status ${status} without an error detail.`;
}

function extractDetail(bodyText: string): unknown {
  if (!bodyText) return null;
  try {
    const data: unknown = JSON.parse(bodyText);
    if (data !== null && typeof data === "object" && "detail" in data) {
      return (data as { detail: unknown }).detail;
    }
  } catch {
    // Non-JSON body: tolerated, detail stays null.
  }
  return null;
}

/** Map a non-2xx response onto the typed error hierarchy. */
export function errorFromResponse(
  status: number,
  headers: Headers | HeadersLike | undefined,
  bodyText: string
): APIStatusError {
  const normalizedHeaders = headersToRecord(headers);
  const bodySummary = bodyText ? bodyText.slice(0, BODY_SUMMARY_LIMIT) : null;
  const detail = extractDetail(bodyText);
  const message = messageFor(detail, status);
  const options: APIStatusErrorOptions = {
    status,
    headers: normalizedHeaders,
    body: bodySummary,
  };

  if (status === 401) return new AuthenticationError(message, options);
  if (status === 402) {
    let balance: number | null = null;
    let required: number | null = null;
    if (typeof detail === "string") {
      const balanceMatch = BALANCE_RE.exec(detail);
      if (balanceMatch) balance = parseNumber(balanceMatch[1]);
      const requiredMatch = REQUIRED_RE.exec(detail);
      if (requiredMatch) required = parseNumber(requiredMatch[1]);
    } else if (detail !== null && typeof detail === "object" && !Array.isArray(detail)) {
      // Tolerate structured details: {"detail": {"balance": ..., "required": ...}}
      const structured = detail as Record<string, unknown>;
      balance = parseNumber(structured["balance"]);
      required = parseNumber(structured["required"]);
    }
    return new InsufficientCreditsError(message, { ...options, balance, required });
  }
  if (status === 403) return new EmailNotVerifiedError(message, options);
  if (status === 422) return new ValidationError(message, options);
  if (status === 429) {
    return new RateLimitError(message, {
      ...options,
      retryAfter: parseRetryAfter(normalizedHeaders),
    });
  }
  if (status === 400) return new BadRequestError(message, options);
  if (status >= 500) return new SearchPipeServerError(message, options);
  return new APIStatusError(message, options);
}
