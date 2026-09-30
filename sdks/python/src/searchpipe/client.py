"""Thin HTTP clients for the SearchPipe web search API.

``SearchPipe`` (sync, httpx.Client) and ``AsyncSearchPipe`` (httpx.AsyncClient)
cover the full ``POST /search`` parameter set and map non-2xx responses onto
the typed exception hierarchy in :mod:`searchpipe.exceptions`.

The ``transport=`` constructor parameter exists **for tests only** (httpx
``MockTransport`` injection); never use it in application code.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from .exceptions import (
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
    _parse_number,
)
from .models import SearchResponse

__all__ = ["SearchPipe", "AsyncSearchPipe", "DEFAULT_BASE_URL"]

DEFAULT_BASE_URL = "https://searchpipe.tech"
ENV_API_KEY = "SEARCHPIPE_API_KEY"
ENV_BASE_URL = "SEARCHPIPE_BASE_URL"

_BALANCE_RE = re.compile(r"balance\s+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_REQUIRED_RE = re.compile(r"requires\s+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)

_BODY_SUMMARY_LIMIT = 500


def _search_payload(
    query: str,
    *,
    max_results: int,
    search_depth: str,
    include_answer: bool,
    include_raw_content: bool,
) -> dict[str, Any]:
    """Build the JSON request body, mirroring the server's snake_case schema."""
    return {
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": include_answer,
        "include_raw_content": include_raw_content,
    }


def _error_detail(response: httpx.Response) -> tuple[Any, str | None]:
    """Extract ``(detail, body_summary)`` from an error response.

    ``detail`` is the JSON body's ``detail`` field when the body is a JSON
    object (string, dict, or list — FastAPI attaches dicts for custom errors
    and lists for 422 validation); non-JSON bodies are tolerated and leave
    ``detail`` as ``None``.
    """
    raw = response.text or ""
    body_summary = raw[:_BODY_SUMMARY_LIMIT] if raw else None
    detail: Any = None
    try:
        data: Any = response.json()
    except ValueError:
        data = None
    if isinstance(data, dict) and "detail" in data:
        detail = data["detail"]
    return detail, body_summary


def _message_for(detail: Any, status_code: int) -> str:
    if isinstance(detail, str) and detail:
        return detail
    if isinstance(detail, (dict, list)) and detail:
        return json.dumps(detail, ensure_ascii=False)
    return f"SearchPipe API returned status {status_code} without an error detail."


def _error_from_response(response: httpx.Response) -> APIStatusError:
    """Map a non-2xx response onto the typed exception hierarchy."""
    status_code = response.status_code
    detail, body_summary = _error_detail(response)
    message = _message_for(detail, status_code)
    headers = response.headers
    kwargs: dict[str, Any] = {"status_code": status_code, "body": body_summary, "headers": headers}

    if status_code == 401:
        return AuthenticationError(message, **kwargs)
    if status_code == 402:
        balance: float | None = None
        required: float | None = None
        if isinstance(detail, str):
            m = _BALANCE_RE.search(detail)
            if m:
                balance = _parse_number(m.group(1))
            m = _REQUIRED_RE.search(detail)
            if m:
                required = _parse_number(m.group(1))
        elif isinstance(detail, dict):
            # Tolerate structured details: {"detail": {"balance": ..., "required": ...}}
            balance = _parse_number(detail.get("balance"))
            required = _parse_number(detail.get("required"))
        return InsufficientCreditsError(message, balance=balance, required=required, **kwargs)
    if status_code == 403:
        return EmailNotVerifiedError(message, **kwargs)
    if status_code == 422:
        return ValidationError(message, **kwargs)
    if status_code == 429:
        retry_after: int | str | None = None
        raw_retry_after = headers.get("retry-after")
        if raw_retry_after is not None:
            try:
                retry_after = int(raw_retry_after.strip())
            except ValueError:
                retry_after = raw_retry_after
        return RateLimitError(message, retry_after=retry_after, **kwargs)
    if status_code == 400:
        return BadRequestError(message, **kwargs)
    if status_code >= 500:
        return SearchPipeServerError(message, **kwargs)
    return APIStatusError(message, **kwargs)


class _BaseClient:
    """Shared configuration logic for the sync and async clients."""

    def _resolve_config(
        self,
        api_key: str | None,
        base_url: str | None,
        timeout: float,
    ) -> tuple[str, str, float]:
        if not api_key:
            api_key = os.environ.get(ENV_API_KEY)
        if not api_key:
            raise SearchPipeError(
                "Missing API key: pass api_key=... or set the SEARCHPIPE_API_KEY "
                "environment variable. Get a key at https://searchpipe.tech"
            )
        if not base_url:
            base_url = os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL
        return api_key, base_url.rstrip("/"), timeout


class SearchPipe(_BaseClient):
    """Synchronous client for the SearchPipe web search API.

    Args:
        api_key: API key (``sp-...``). Falls back to the ``SEARCHPIPE_API_KEY``
            environment variable; raises :class:`SearchPipeError` when neither
            is set.
        base_url: API base URL. Falls back to ``SEARCHPIPE_BASE_URL``, then to
            ``https://searchpipe.tech``. Override it to target a self-hosted
            instance. Trailing slashes are stripped.
        timeout: Default request timeout in seconds.
        transport: **For tests only** — inject an ``httpx.BaseTransport``
            (e.g. ``httpx.MockTransport``) instead of a real connection.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        api_key, base_url, timeout = self._resolve_config(api_key, base_url, timeout)
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    @property
    def base_url(self) -> str:
        """Effective base URL (trailing slash stripped)."""
        return self._base_url

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = False,
        include_raw_content: bool = False,
        timeout: float | None = None,
    ) -> SearchResponse:
        """Run a web search via ``POST /search``.

        Args:
            query: The search query.
            max_results: Maximum number of results (server accepts 1-20).
            search_depth: ``"basic"`` (1 credit) or ``"advanced"`` (2 credits).
            include_answer: Generate an LLM answer with citations.
            include_raw_content: Include full fetched page content.
            timeout: Per-request timeout override; ``None`` uses the client
                default.

        Returns:
            A typed :class:`~searchpipe.models.SearchResponse`.

        Raises:
            SearchPipeError: Subclasses per the error contract — see
                :mod:`searchpipe.exceptions`.
        """
        payload = _search_payload(
            query,
            max_results=max_results,
            search_depth=search_depth,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )
        options: dict[str, Any] = {}
        if timeout is not None:
            options["timeout"] = timeout
        try:
            response = self._client.post("/search", json=payload, **options)
        except httpx.RequestError as exc:
            raise APIConnectionError(
                f"Could not connect to SearchPipe at {self._base_url}: {exc}"
            ) from exc
        return self._process(response)

    def _process(self, response: httpx.Response) -> SearchResponse:
        if not response.is_success:
            raise _error_from_response(response)
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise SearchPipeError(
                f"SearchPipe returned a non-JSON success response "
                f"(HTTP {response.status_code})."
            ) from exc
        if not isinstance(data, dict):
            raise SearchPipeError("SearchPipe returned an unexpected response format.")
        return SearchResponse.from_dict(data)

    def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> SearchPipe:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class AsyncSearchPipe(_BaseClient):
    """Asynchronous client for the SearchPipe web search API.

    Mirrors :class:`SearchPipe` with an ``httpx.AsyncClient``; ``search`` is
    awaited. The ``transport=`` parameter is **for tests only**.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        api_key, base_url, timeout = self._resolve_config(api_key, base_url, timeout)
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    @property
    def base_url(self) -> str:
        """Effective base URL (trailing slash stripped)."""
        return self._base_url

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = False,
        include_raw_content: bool = False,
        timeout: float | None = None,
    ) -> SearchResponse:
        """Run a web search via ``POST /search`` (awaited). See :meth:`SearchPipe.search`."""
        payload = _search_payload(
            query,
            max_results=max_results,
            search_depth=search_depth,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
        )
        options: dict[str, Any] = {}
        if timeout is not None:
            options["timeout"] = timeout
        try:
            response = await self._client.post("/search", json=payload, **options)
        except httpx.RequestError as exc:
            raise APIConnectionError(
                f"Could not connect to SearchPipe at {self._base_url}: {exc}"
            ) from exc
        return self._process(response)

    def _process(self, response: httpx.Response) -> SearchResponse:
        if not response.is_success:
            raise _error_from_response(response)
        try:
            data: Any = response.json()
        except ValueError as exc:
            raise SearchPipeError(
                f"SearchPipe returned a non-JSON success response "
                f"(HTTP {response.status_code})."
            ) from exc
        if not isinstance(data, dict):
            raise SearchPipeError("SearchPipe returned an unexpected response format.")
        return SearchResponse.from_dict(data)

    async def close(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> AsyncSearchPipe:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()
