"""Exception hierarchy mapping the SearchPipe web search API error contract.

Every non-2xx ``/search`` response is mapped to a typed exception:

- ``401`` -> :class:`AuthenticationError`
- ``402`` -> :class:`InsufficientCreditsError` (with ``balance`` / ``required``)
- ``403`` -> :class:`EmailNotVerifiedError`
- ``422`` -> :class:`ValidationError` (subclass of :class:`BadRequestError`)
- ``429`` -> :class:`RateLimitError` (with ``retry_after`` from ``Retry-After``)
- ``400`` -> :class:`BadRequestError`
- ``>=500`` -> :class:`SearchPipeServerError`
- other -> :class:`APIStatusError`

Network-level failures (DNS, refused connection, timeouts) raise
:class:`APIConnectionError`.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "SearchPipeError",
    "APIConnectionError",
    "APIStatusError",
    "AuthenticationError",
    "EmailNotVerifiedError",
    "InsufficientCreditsError",
    "RateLimitError",
    "BadRequestError",
    "ValidationError",
    "SearchPipeServerError",
]


class SearchPipeError(Exception):
    """Base class for every error raised by this SDK."""


class APIConnectionError(SearchPipeError):
    """Network failure: DNS error, connection refused/reset, or timeout."""


class APIStatusError(SearchPipeError):
    """The API returned a non-2xx HTTP status.

    Attributes:
        status_code: HTTP status code of the response.
        message: Human-readable error message (the JSON ``detail`` when present).
        body: Readable summary of the raw response body (truncated), or ``None``.
        headers: Response headers (lower-cased keys), useful for e.g. rate limits.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.body = body
        self.headers: dict[str, str] = dict(headers) if headers else {}


class AuthenticationError(APIStatusError):
    """HTTP 401: the API key is missing, malformed, or revoked."""


class EmailNotVerifiedError(APIStatusError):
    """HTTP 403: the account's email address has not been verified yet."""


class InsufficientCreditsError(APIStatusError):
    """HTTP 402: the account does not have enough credits for this call.

    ``balance`` and ``required`` are parsed from the error ``detail`` when the
    server provides them (as numbers or text); otherwise they are ``None``.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: str | None = None,
        headers: Mapping[str, str] | None = None,
        balance: float | None = None,
        required: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body, headers=headers)
        self.balance = balance
        self.required = required


class RateLimitError(APIStatusError):
    """HTTP 429: request rate limit exceeded.

    ``retry_after`` mirrors the ``Retry-After`` response header (seconds as an
    ``int`` when parseable, otherwise the raw header string); ``None`` when the
    server did not send the header.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        body: str | None = None,
        headers: Mapping[str, str] | None = None,
        retry_after: int | str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body, headers=headers)
        self.retry_after = retry_after


class BadRequestError(APIStatusError):
    """HTTP 400: the request (or the generated output) was rejected."""


class ValidationError(BadRequestError):
    """HTTP 422: request validation failed (FastAPI/pydantic contract).

    Deliberately a subclass of :class:`BadRequestError`: catching
    ``BadRequestError`` also catches validation failures, while this class
    lets 422 be handled specifically.
    """


class SearchPipeServerError(APIStatusError):
    """HTTP 5xx: an upstream/internal failure on the SearchPipe side."""


def _parse_number(value: Any) -> float | None:
    """Best-effort conversion to float; ``None`` when not numeric."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            return None
    return None
