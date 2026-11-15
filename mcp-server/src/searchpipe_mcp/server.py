"""SearchPipe MCP server (stdio) — a thin local proxy over the SearchPipe web search API.

Tool listing (initialize / tools/list) works offline and without an API key. Tool calls
require ``SEARCHPIPE_API_KEY`` (``sp-…`` — create a free key at
https://searchpipe.tech/dashboard/api-keys) and hit the same commercial pipeline as the
REST API: authentication, rate limiting, input/output moderation, per-call credit
billing and automatic refund on failure.
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

DEFAULT_BASE_URL = "https://searchpipe.tech"
ENV_API_KEY = "SEARCHPIPE_API_KEY"
ENV_BASE_URL = "SEARCHPIPE_BASE_URL"

mcp = FastMCP("searchpipe")


def _require_key() -> tuple[str, str]:
    """Return (api_key, base_url); raise a descriptive error when the key is missing."""
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not api_key:
        raise ValueError(
            "Missing SearchPipe API key: set the SEARCHPIPE_API_KEY environment "
            "variable (create a free key at https://searchpipe.tech/dashboard/api-keys)"
        )
    base_url = os.environ.get(ENV_BASE_URL, DEFAULT_BASE_URL).rstrip("/")
    return api_key, base_url


def _headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _clean_payload(**params: Any) -> dict[str, Any]:
    """Drop None values so omitted optional parameters keep server defaults."""
    return {k: v for k, v in params.items() if v is not None}


async def _post(api_key: str, base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{base_url}{path}", json=payload, headers=_headers(api_key)
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"SearchPipe API {resp.status_code}: {resp.text[:500]}")
    return resp.json()


@mcp.tool(annotations={"title": "SearchPipe Web Search", "readOnlyHint": True})
async def searchpipe_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = False,
    include_raw_content: bool = False,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    topic: str = "general",
    country: str | None = None,
    language: str | None = None,
    safe_search: int = 0,
    include_images: bool = False,
) -> dict[str, Any]:
    """Run a web search: ranked results with source URLs and an optional AI answer.

    Accepts the same parameters as the HTTP POST /search endpoint and runs on the same
    commercial pipeline (authentication, rate limiting, moderation, per-call credit
    billing, refund on failure). Credits are charged per call: search_depth "basic"
    (default) costs 1 credit, "advanced" costs 2, "fast" costs 0.5 and skips all LLM
    steps (results keep engine order, no answer is generated).

    max_results: 1-20 (default 5). include_domains / exclude_domains: restrict or
    exclude domains ("example.com" matches the domain and any subdomain; exclude wins
    over include). time_range: "day" / "week" / "month" / "year"; start_date /
    end_date: ISO YYYY-MM-DD bounds. topic: "general" / "news". country / language:
    ISO country and language codes for localization. safe_search: 0-3.
    """
    api_key, base_url = _require_key()
    payload = _clean_payload(
        query=query,
        max_results=max_results,
        search_depth=search_depth,
        include_answer=include_answer,
        include_raw_content=include_raw_content,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        topic=topic,
        country=country,
        language=language,
        safe_search=safe_search,
        include_images=include_images,
    )
    return await _post(api_key, base_url, "/search", payload)


@mcp.tool(annotations={"title": "SearchPipe Verify", "readOnlyHint": True})
async def searchpipe_verify(
    claim: str,
    mode: str = "auto",
    evidence_urls: list[str] | None = None,
    max_evidence: int = 5,
) -> dict[str, Any]:
    """Verify a factual claim against retrieved evidence: claim in, verdict out.

    Returns a four-label judgment — supported / partial / unsupported / inconclusive —
    with span-level evidence quotes and source URLs, not generated text. Every result
    ships with verifiable evidence — span-level quotes, claim verdicts, and source
    authority — not just links. Verification fetches source pages, so expect the call
    to take 5-15 seconds. An inconclusive verdict is a delivered result and is not
    refunded.

    mode: evidence route — "paper" / "web" / "auto" (default; a DOI or arXiv signal
    decides). evidence_urls: up to 5 caller-supplied citations to verify.
    max_evidence: maximum evidence items to return (1-10, default 5).
    """
    api_key, base_url = _require_key()
    payload = _clean_payload(
        claim=claim,
        mode=mode,
        evidence_urls=evidence_urls,
        max_evidence=max_evidence,
    )
    return await _post(api_key, base_url, "/verify", payload)


@mcp.tool(annotations={"title": "SearchPipe Account Balance", "readOnlyHint": True})
async def searchpipe_account_balance() -> dict[str, Any]:
    """Check the remaining credit balance for the configured API key — free to call.

    Returns balance (total remaining credits), permanent (recharge/bonus credits that
    never expire), expiring (subscription credits, valid 30 days), next_expiry, and
    free_tier_credits. Poll this before batch jobs to avoid hitting 402
    insufficient-credits mid-run.
    """
    api_key, base_url = _require_key()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{base_url}/v1/account/balance", headers=_headers(api_key)
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"SearchPipe API {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def main() -> None:
    """Run the SearchPipe MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
