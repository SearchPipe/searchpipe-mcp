"""Response dataclasses for the SearchPipe web search API.

Mirrors the server's ``SearchResponse`` schema (``/search`` endpoint):
tolerant of missing fields so minor server additions never break older SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """A single ranked result."""

    url: str
    title: str
    content: str = ""
    score: float = 0.0
    raw_content: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SearchResult:
        """Build a result from a raw JSON object, tolerating missing fields."""
        raw_content = d.get("raw_content")
        return cls(
            url=str(d.get("url", "")),
            title=str(d.get("title", "")),
            content=str(d.get("content", "")),
            score=float(d.get("score", 0.0) or 0.0),
            raw_content=None if raw_content is None else str(raw_content),
        )


@dataclass
class SearchResponse:
    """Response of ``POST /search``."""

    query: str
    answer: str | None = None
    results: list[SearchResult] = field(default_factory=list)
    ai_generated: bool = False

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SearchResponse:
        """Build a response from raw JSON, tolerating missing fields."""
        results_raw = d.get("results") or []
        results = [
            r if isinstance(r, SearchResult) else SearchResult.from_dict(r)
            for r in results_raw
        ]
        return cls(
            query=str(d.get("query", "")),
            answer=None if d.get("answer") is None else str(d["answer"]),
            results=results,
            ai_generated=bool(d.get("ai_generated", False)),
        )
