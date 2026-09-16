"""Shared client / models for the SearchPipe LangChain integration."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from langchain_core.utils import get_from_dict_or_env


class SearchPipeAPIError(Exception):
    """Raised when the SearchPipe API returns a non-2xx response."""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"SearchPipe API error {status_code}: {body[:500]}")


class SearchPipeClient:
    """Thin async-capable HTTP client for the SearchPipe ``/search`` endpoint.

    Parameters
    ----------
    api_key:
        SearchPipe API key (``sp-...``). Falls back to the
        ``SEARCHPIPE_API_KEY`` environment variable when omitted.
    base_url:
        Root URL of the SearchPipe instance. Defaults to the hosted service
        (``https://searchpipe.tech``); override for self-hosted deployments.
    timeout:
        Per-request timeout in seconds.
    """

    DEFAULT_BASE_URL = "https://searchpipe.tech"

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("SEARCHPIPE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "SearchPipe API key is required. Pass `api_key=` or set the "
                "SEARCHPIPE_API_KEY environment variable. Get a key at "
                "https://searchpipe.tech/dashboard/api-keys"
            )
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    # -- HTTP plumbing ------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _url(self) -> str:
        return f"{self.base_url}/search"

    # -- public API ---------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = False,
        include_raw_content: bool = False,
    ) -> dict[str, Any]:
        """Synchronous search call. Returns the decoded JSON body."""
        payload: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self._url(), json=payload, headers=self._headers())
        if resp.status_code != 200:
            raise SearchPipeAPIError(resp.status_code, resp.text)
        return resp.json()

    async def asearch(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = False,
        include_raw_content: bool = False,
    ) -> dict[str, Any]:
        """Asynchronous search call. Returns the decoded JSON body."""
        payload: dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self._url(), json=payload, headers=self._headers())
        if resp.status_code != 200:
            raise SearchPipeAPIError(resp.status_code, resp.text)
        return resp.json()


def resolve_api_key(api_key: Optional[str]) -> str:
    """Resolve the API key from argument or environment, LangChain-style."""
    return get_from_dict_or_env(
        {"api_key": api_key} if api_key else {},
        "api_key",
        "SEARCHPIPE_API_KEY",
    )
