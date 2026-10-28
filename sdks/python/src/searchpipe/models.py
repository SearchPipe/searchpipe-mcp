"""Response dataclasses for the SearchPipe web search API.

Mirrors the server's ``SearchResponse`` (``/search``) and ``VerifyResponse``
(``/verify``) schemas: tolerant of missing fields so minor server additions
never break older SDKs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _opt(value: Any, cast: type) -> Any:
    """Best-effort conversion; ``None`` passes through, garbage becomes ``None``."""
    if value is None:
        return None
    try:
        return cast(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ResultEvidence:
    """Verbatim evidence attached to a search result.

    Mirrors the server's ``ResultEvidence``: ``quote`` is a supporting
    sentence quoted from the fetched page; ``span_start`` / ``span_end``
    are character offsets into ``raw_content`` (or ``content`` when the
    page body was not fetched). Populated when the deployment enables
    search evidence; ``None`` otherwise.
    """

    quote: str = ""
    span_start: int | None = None
    span_end: int | None = None
    source_tier: str = "unknown"
    fetch_status: int | None = None
    redirected: bool = False
    final_url: str | None = None
    fetched_at: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ResultEvidence:
        """Build an evidence object from raw JSON, tolerating missing fields."""
        return cls(
            quote=str(d.get("quote", "")),
            span_start=_opt(d.get("span_start"), int),
            span_end=_opt(d.get("span_end"), int),
            source_tier=str(d.get("source_tier") or "unknown"),
            fetch_status=_opt(d.get("fetch_status"), int),
            redirected=bool(d.get("redirected", False)),
            final_url=None if d.get("final_url") is None else str(d["final_url"]),
            fetched_at=None if d.get("fetched_at") is None else str(d["fetched_at"]),
        )


@dataclass
class StatementCitation:
    """The cited result backing one audited statement."""

    url: str
    title: str | None = None
    quote: str | None = None
    span_start: int | None = None
    span_end: int | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StatementCitation:
        return cls(
            url=str(d.get("url", "")),
            title=None if d.get("title") is None else str(d["title"]),
            quote=None if d.get("quote") is None else str(d["quote"]),
            span_start=_opt(d.get("span_start"), int),
            span_end=_opt(d.get("span_end"), int),
        )


@dataclass
class StatementAudit:
    """Per-statement audit of an AI answer.

    ``verdict`` is one of ``supported`` / ``partial`` / ``unsupported`` /
    ``inconclusive`` (judged against the cited source) or ``uncited``
    (the statement carried no citation marker and was not judged).
    """

    text: str
    verdict: str
    confidence: float = 0.0
    citations: list[StatementCitation] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> StatementAudit:
        citations_raw = d.get("citations") or []
        citations = [
            c if isinstance(c, StatementCitation) else StatementCitation.from_dict(c)
            for c in citations_raw
        ]
        return cls(
            text=str(d.get("text", "")),
            verdict=str(d.get("verdict", "")),
            confidence=_opt(d.get("confidence"), float) or 0.0,
            citations=citations,
        )


@dataclass
class AnswerAudit:
    """Per-statement audit of the AI answer (advanced depth only).

    ``score`` is the fraction of judged statements that are supported
    (0-1); ``uncited_count`` counts statements without any citation
    marker; ``prompt_version`` identifies the audit judge prompt.
    """

    score: float = 0.0
    uncited_count: int = 0
    statements: list[StatementAudit] = field(default_factory=list)
    prompt_version: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AnswerAudit:
        statements_raw = d.get("statements") or []
        statements = [
            s if isinstance(s, StatementAudit) else StatementAudit.from_dict(s)
            for s in statements_raw
        ]
        return cls(
            score=_opt(d.get("score"), float) or 0.0,
            uncited_count=_opt(d.get("uncited_count"), int) or 0,
            statements=statements,
            prompt_version=str(d.get("prompt_version", "")),
        )


@dataclass
class SearchResult:
    """A single ranked result."""

    url: str
    title: str
    content: str = ""
    score: float = 0.0
    raw_content: str | None = None
    evidence: ResultEvidence | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SearchResult:
        """Build a result from a raw JSON object, tolerating missing fields."""
        raw_content = d.get("raw_content")
        evidence = d.get("evidence")
        return cls(
            url=str(d.get("url", "")),
            title=str(d.get("title", "")),
            content=str(d.get("content", "")),
            score=float(d.get("score", 0.0) or 0.0),
            raw_content=None if raw_content is None else str(raw_content),
            evidence=(
                None if evidence is None
                else evidence if isinstance(evidence, ResultEvidence)
                else ResultEvidence.from_dict(evidence)
            ),
        )


@dataclass
class SearchResponse:
    """Response of ``POST /search``."""

    query: str
    answer: str | None = None
    results: list[SearchResult] = field(default_factory=list)
    ai_generated: bool = False
    answer_audit: AnswerAudit | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SearchResponse:
        """Build a response from raw JSON, tolerating missing fields."""
        results_raw = d.get("results") or []
        results = [
            r if isinstance(r, SearchResult) else SearchResult.from_dict(r)
            for r in results_raw
        ]
        answer_audit = d.get("answer_audit")
        return cls(
            query=str(d.get("query", "")),
            answer=None if d.get("answer") is None else str(d["answer"]),
            results=results,
            ai_generated=bool(d.get("ai_generated", False)),
            answer_audit=(
                None if answer_audit is None
                else answer_audit if isinstance(answer_audit, AnswerAudit)
                else AnswerAudit.from_dict(answer_audit)
            ),
        )


@dataclass
class VerifyEvidence:
    """A single piece of evidence backing a claim verdict.

    ``quote`` is a span-level quote from the source text; ``span_start`` /
    ``span_end`` are character offsets inside the fetched page content.
    """

    url: str
    title: str | None = None
    source_tier: str = "unknown"
    quote: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    per_evidence_verdict: str | None = None
    confidence: float | None = None
    url_health: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VerifyEvidence:
        """Build an evidence item from raw JSON, tolerating missing fields."""
        url_health = d.get("url_health")
        return cls(
            url=str(d.get("url", "")),
            title=None if d.get("title") is None else str(d["title"]),
            source_tier=str(d.get("source_tier") or "unknown"),
            quote=None if d.get("quote") is None else str(d["quote"]),
            span_start=_opt(d.get("span_start"), int),
            span_end=_opt(d.get("span_end"), int),
            per_evidence_verdict=(
                None if d.get("per_evidence_verdict") is None
                else str(d["per_evidence_verdict"])
            ),
            confidence=_opt(d.get("confidence"), float),
            url_health=url_health if isinstance(url_health, dict) else None,
        )


@dataclass
class VerifyResponse:
    """Response of ``POST /verify``: four-label claim verdict with evidence.

    ``verdict`` is one of ``supported`` / ``partial`` / ``unsupported`` /
    ``inconclusive``; ``reason_code`` is a machine-readable template phrase
    (never free-generated text); ``timing`` maps pipeline stages to seconds.
    """

    verdict: str
    confidence: float = 0.0
    reason_code: str = ""
    evidences: list[VerifyEvidence] = field(default_factory=list)
    timing: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> VerifyResponse:
        """Build a response from raw JSON, tolerating missing fields."""
        evidences_raw = d.get("evidences") or []
        evidences = [
            e if isinstance(e, VerifyEvidence) else VerifyEvidence.from_dict(e)
            for e in evidences_raw
        ]
        timing_raw = d.get("timing")
        timing: dict[str, float] = {}
        if isinstance(timing_raw, dict):
            for k, v in timing_raw.items():
                parsed = _opt(v, float)
                if parsed is not None:
                    timing[str(k)] = parsed
        return cls(
            verdict=str(d.get("verdict", "")),
            confidence=_opt(d.get("confidence"), float) or 0.0,
            reason_code=str(d.get("reason_code", "")),
            evidences=evidences,
            timing=timing,
        )
