"""SDK unit tests — httpx MockTransport, zero real network."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import httpx
import pytest

from searchpipe import (
    APIConnectionError,
    APIStatusError,
    AsyncSearchPipe,
    AuthenticationError,
    BadRequestError,
    EmailNotVerifiedError,
    InsufficientCreditsError,
    RateLimitError,
    SearchPipe,
    SearchPipeError,
    SearchPipeServerError,
    SearchResponse,
    SearchResult,
    ValidationError,
    VerifyEvidence,
    VerifyResponse,
    __version__,
)


def success_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "query": "python httpx",
        "answer": None,
        "ai_generated": False,
        "results": [
            {
                "url": "https://example.com/a",
                "title": "A",
                "content": "snippet a",
                "score": 0.9,
                "raw_content": "full text a",
            },
            {
                "url": "https://example.com/b",
                "title": "B",
                "content": "snippet b",
                "score": 0.5,
                "raw_content": None,
            },
        ],
    }
    body.update(overrides)
    return body


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    captured: list[httpx.Request] | None = None,
    **kwargs: Any,
) -> SearchPipe:
    """Build a sync client on a MockTransport; optionally capture requests."""

    def wrapped(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return handler(request)

    kwargs.setdefault("api_key", "sp-test-key")
    return SearchPipe(transport=httpx.MockTransport(wrapped), **kwargs)


def error_response(
    status_code: int,
    json_body: dict[str, Any] | None = None,
    text: str | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    return httpx.Response(status_code, json=json_body, text=text, headers=headers)


# --- version / exports -------------------------------------------------------


def test_version_and_public_names():
    assert __version__ == "2.0.0"
    import searchpipe

    for name in searchpipe.__all__:
        assert getattr(searchpipe, name) is not None


# --- success paths ------------------------------------------------------------


def test_search_success_without_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body())

    resp = make_client(handler).search("python httpx")
    assert isinstance(resp, SearchResponse)
    assert resp.query == "python httpx"
    assert resp.answer is None
    assert resp.ai_generated is False
    assert len(resp.results) == 2
    first = resp.results[0]
    assert isinstance(first, SearchResult)
    assert first.url == "https://example.com/a"
    assert first.title == "A"
    assert first.content == "snippet a"
    assert first.score == 0.9
    assert first.raw_content == "full text a"
    assert resp.results[1].raw_content is None


def test_search_success_with_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=success_body(answer="42", ai_generated=True),
        )

    resp = make_client(handler).search("meaning of life", include_answer=True)
    assert resp.answer == "42"
    assert resp.ai_generated is True


def test_search_response_tolerates_missing_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        # No answer / ai_generated keys at all; result missing score/content.
        return httpx.Response(
            200,
            json={"query": "q", "results": [{"url": "u", "title": "t"}]},
        )

    resp = make_client(handler).search("q")
    assert resp.answer is None
    assert resp.ai_generated is False
    assert resp.results[0].score == 0.0
    assert resp.results[0].content == ""
    assert resp.results[0].raw_content is None
    assert resp.results[0].evidence is None
    assert resp.answer_audit is None


def test_search_evidence_and_answer_audit_map_typed_fields():
    body = success_body(
        answer_audit={
            "score": 0.75,
            "uncited_count": 1,
            "prompt_version": "answer-audit-v1-20261015",
            "statements": [
                {
                    "text": "The sky is blue.",
                    "verdict": "supported",
                    "confidence": 0.97,
                    "citations": [
                        {
                            "url": "https://example.com/a",
                            "title": "A",
                            "quote": "sky quote",
                            "span_start": 3,
                            "span_end": 12,
                        }
                    ],
                },
                {"text": "Uncited claim.", "verdict": "uncited", "confidence": 0.0},
            ],
        }
    )
    body["results"][0]["evidence"] = {
        "quote": "full text a",
        "span_start": 0,
        "span_end": 11,
        "source_tier": "official",
        "fetch_status": 200,
        "redirected": True,
        "final_url": "https://example.com/a-final",
        "fetched_at": "2026-10-19T00:00:00Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    resp = make_client(handler).search("q", include_answer=True, search_depth="advanced")
    audit = resp.answer_audit
    assert audit is not None
    assert audit.score == 0.75
    assert audit.uncited_count == 1
    assert audit.prompt_version == "answer-audit-v1-20261015"
    first = audit.statements[0]
    assert first.verdict == "supported"
    assert first.citations[0].url == "https://example.com/a"
    assert first.citations[0].span_end == 12
    assert audit.statements[1].verdict == "uncited"

    evidence = resp.results[0].evidence
    assert evidence is not None
    assert evidence.quote == "full text a"
    assert evidence.source_tier == "official"
    assert evidence.fetch_status == 200
    assert evidence.redirected is True
    assert evidence.final_url == "https://example.com/a-final"
    assert resp.results[1].evidence is None


# --- error contract mapping ----------------------------------------------------


def test_error_401_maps_to_authentication_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(401, json_body={"detail": "Invalid API key"})

    with pytest.raises(AuthenticationError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 401
    assert str(excinfo.value) == "Invalid API key"
    assert isinstance(excinfo.value, APIStatusError)


def test_error_403_maps_to_email_not_verified_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(403, json_body={"detail": "Email not verified"})

    with pytest.raises(EmailNotVerifiedError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 403
    assert "Email not verified" in str(excinfo.value)


def test_error_402_parses_balance_and_required_from_text_detail():
    detail = "Insufficient credits: balance 3.5, this call requires 5.0"

    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(402, json_body={"detail": detail})

    with pytest.raises(InsufficientCreditsError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 402
    assert excinfo.value.balance == 3.5
    assert excinfo.value.required == 5.0
    assert "balance 3.5" in str(excinfo.value)


def test_error_402_parses_structured_dict_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(
            402, json_body={"detail": {"balance": 12, "required": 15}}
        )

    with pytest.raises(InsufficientCreditsError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.balance == 12.0
    assert excinfo.value.required == 15.0


def test_error_402_tolerates_unparseable_detail():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(402, json_body={"detail": "no numbers here"})

    with pytest.raises(InsufficientCreditsError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.balance is None
    assert excinfo.value.required is None


def test_error_429_with_retry_after_header():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(
            429,
            json_body={"detail": "Rate limit exceeded"},
            headers={"Retry-After": "60"},
        )

    with pytest.raises(RateLimitError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 429
    assert excinfo.value.retry_after == 60


def test_error_429_without_retry_after_header():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(429, json_body={"detail": "Rate limit exceeded"})

    with pytest.raises(RateLimitError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.retry_after is None


def test_error_400_maps_to_bad_request_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(
            400, json_body={"detail": "Output content violation: ['violence']"}
        )

    with pytest.raises(BadRequestError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 400
    assert "Output content violation" in str(excinfo.value)


def test_error_422_maps_to_validation_error_subclass_of_bad_request():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(
            422,
            json_body={"detail": [{"loc": ["body", "max_results"], "msg": "less_equal"}]},
        )

    with pytest.raises(ValidationError) as excinfo:
        make_client(handler).search("q", max_results=99)
    assert excinfo.value.status_code == 422
    # 422 is deliberately also catchable as BadRequestError.
    assert isinstance(excinfo.value, BadRequestError)
    assert "max_results" in str(excinfo.value)


def test_error_502_maps_to_server_error_with_body_summary():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(
            502, json_body={"detail": "Search backend failure: upstream unavailable"}
        )

    with pytest.raises(SearchPipeServerError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 502
    assert "Search backend failure" in str(excinfo.value)
    assert excinfo.value.body is not None
    assert "Search backend failure" in excinfo.value.body
    assert isinstance(excinfo.value, APIStatusError)


def test_error_other_status_maps_to_generic_api_status_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(418, json_body={"detail": "teapot"})

    with pytest.raises(APIStatusError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 418
    assert str(excinfo.value) == "teapot"
    assert type(excinfo.value) is APIStatusError


def test_error_non_json_body_does_not_crash():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(502, text="<html>Bad Gateway</html>")

    with pytest.raises(SearchPipeServerError) as excinfo:
        make_client(handler).search("q")
    assert excinfo.value.status_code == 502
    # Message falls back to a generic status line; body keeps a readable summary.
    assert "502" in str(excinfo.value)
    assert "Bad Gateway" in excinfo.value.body


def test_connection_error_maps_to_api_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(APIConnectionError) as excinfo:
        make_client(handler).search("q")
    assert not isinstance(excinfo.value, APIStatusError)
    assert "connection refused" in str(excinfo.value)


# --- verify (POST /verify) -----------------------------------------------------


def verify_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "verdict": "supported",
        "confidence": 0.92,
        "reason_code": "quote_span_found",
        "evidences": [
            {
                "url": "https://example.com/paper",
                "title": "Stub Paper",
                "source_tier": "academic",
                "quote": "supporting sentence",
                "span_start": 0,
                "span_end": 19,
                "per_evidence_verdict": "supported",
                "confidence": 0.9,
                "url_health": {
                    "status_code": 200,
                    "redirected": False,
                    "wayback_snapshot": None,
                    "fetched_at": None,
                },
            }
        ],
        "timing": {"v_prepare": 0.01, "v_evidence": 0.4, "v_judge": 0.5},
    }
    body.update(overrides)
    return body


def test_verify_success_maps_typed_response():
    captured: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=verify_body())

    resp = make_client(wrapped, captured=captured).verify(
        "the transformer paper introduced self-attention"
    )
    assert isinstance(resp, VerifyResponse)
    assert resp.verdict == "supported"
    assert resp.confidence == 0.92
    assert resp.reason_code == "quote_span_found"
    assert resp.timing == {"v_prepare": 0.01, "v_evidence": 0.4, "v_judge": 0.5}
    first = resp.evidences[0]
    assert isinstance(first, VerifyEvidence)
    assert first.url == "https://example.com/paper"
    assert first.source_tier == "academic"
    assert first.quote == "supporting sentence"
    assert first.span_start == 0 and first.span_end == 19
    assert first.per_evidence_verdict == "supported"
    assert first.confidence == 0.9
    assert first.url_health is not None
    assert first.url_health["status_code"] == 200

    # Request mapping: POST {base}/verify, claim required, snake_case body.
    import json as _json

    request = captured[0]
    assert request.method == "POST"
    assert str(request.url).endswith("/verify")
    payload = _json.loads(request.read().decode("utf-8"))
    assert payload == {
        "claim": "the transformer paper introduced self-attention",
        "mode": "auto",
    }


def test_verify_request_body_maps_optional_params():
    captured: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=verify_body(verdict="inconclusive"))

    resp = make_client(wrapped, captured=captured).verify(
        "claim",
        mode="paper",
        evidence_urls=["https://example.com/a", "https://example.com/b"],
        max_evidence=3,
    )
    assert resp.verdict == "inconclusive"
    import json as _json

    payload = _json.loads(captured[0].read().decode("utf-8"))
    assert payload == {
        "claim": "claim",
        "mode": "paper",
        "evidence_urls": ["https://example.com/a", "https://example.com/b"],
        "max_evidence": 3,
    }


def test_verify_response_tolerates_missing_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"verdict": "inconclusive"})

    resp = make_client(handler).verify("q")
    assert resp.verdict == "inconclusive"
    assert resp.confidence == 0.0
    assert resp.reason_code == ""
    assert resp.evidences == []
    assert resp.timing == {}


def test_verify_error_401_maps_to_authentication_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(401, json_body={"detail": "Invalid API key"})

    with pytest.raises(AuthenticationError) as excinfo:
        make_client(handler).verify("q")
    assert excinfo.value.status_code == 401


def test_verify_error_402_parses_balance_and_required():
    detail = "Insufficient credits: balance 0.0, this call requires 1.0"

    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(402, json_body={"detail": detail})

    with pytest.raises(InsufficientCreditsError) as excinfo:
        make_client(handler).verify("q")
    assert excinfo.value.status_code == 402
    assert excinfo.value.balance == 0.0
    assert excinfo.value.required == 1.0


def test_verify_error_422_maps_to_validation_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return error_response(
            422,
            json_body={
                "detail": [
                    {
                        "loc": ["body", "claim"],
                        "msg": "String should have at most 2000 characters",
                    }
                ]
            },
        )

    with pytest.raises(ValidationError) as excinfo:
        make_client(handler).verify("x" * 2001)
    assert excinfo.value.status_code == 422
    assert isinstance(excinfo.value, BadRequestError)
    assert "claim" in str(excinfo.value)


def test_async_verify_success():
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=verify_body())

    async def scenario() -> VerifyResponse:
        async with AsyncSearchPipe(
            api_key="sp-test-key", transport=httpx.MockTransport(handler)
        ) as client:
            return await client.verify("async claim", max_evidence=2)

    resp = asyncio.run(scenario())
    assert isinstance(resp, VerifyResponse)
    assert resp.verdict == "supported"
    import json as _json

    payload = _json.loads(captured[0].read().decode("utf-8"))
    assert payload["claim"] == "async claim"
    assert payload["max_evidence"] == 2
    assert captured[0].headers["Authorization"] == "Bearer sp-test-key"


# --- configuration -------------------------------------------------------------


def test_missing_api_key_and_env_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SEARCHPIPE_API_KEY", raising=False)
    with pytest.raises(SearchPipeError):
        SearchPipe()


def test_env_api_key_used(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SEARCHPIPE_API_KEY", "sp-env-key")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body())

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    client = SearchPipe(transport=httpx.MockTransport(wrapped))
    resp = client.search("q")
    assert resp.query == "python httpx"
    assert captured[0].headers["Authorization"] == "Bearer sp-env-key"


def test_env_base_url_used(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SEARCHPIPE_BASE_URL", "https://env.example.com/api/")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body())

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    client = SearchPipe(api_key="sp-test-key", transport=httpx.MockTransport(wrapped))
    assert client.base_url == "https://env.example.com/api"
    client.search("q")
    assert str(captured[0].url).startswith("https://env.example.com/api/search")


def test_default_base_url_overridable_and_trailing_slash_stripped(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("SEARCHPIPE_BASE_URL", raising=False)
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body())

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    client = SearchPipe(
        api_key="sp-test-key",
        base_url="https://selfhost.example.com///",
        transport=httpx.MockTransport(wrapped),
    )
    assert client.base_url == "https://selfhost.example.com"
    client.search("q")
    request = captured[0]
    assert str(request.url) == "https://selfhost.example.com/search"
    assert request.headers["Authorization"] == "Bearer sp-test-key"


# --- request body mapping --------------------------------------------------------


def test_request_body_maps_all_parameters():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body())

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    client = make_client(wrapped, captured=captured)
    client.search(
        "rust vs go",
        max_results=10,
        search_depth="advanced",
        include_answer=True,
        include_raw_content=True,
    )
    body = captured[0].read().decode("utf-8")
    import json as _json

    payload = _json.loads(body)
    assert payload == {
        "query": "rust vs go",
        "max_results": 10,
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": True,
    }
    assert captured[0].method == "POST"


def test_default_request_body_values():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body())

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    make_client(wrapped, captured=captured).search("q")
    import json as _json

    payload = _json.loads(captured[0].read().decode("utf-8"))
    assert payload["max_results"] == 5
    assert payload["search_depth"] == "basic"
    assert payload["include_answer"] is False
    assert payload["include_raw_content"] is False


# --- async client -----------------------------------------------------------------


def test_async_search_success():
    captured: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=success_body(answer="hi", ai_generated=True))

    async def scenario() -> SearchResponse:
        async with AsyncSearchPipe(
            api_key="sp-test-key", transport=httpx.MockTransport(handler)
        ) as client:
            return await client.search("async q", include_answer=True)

    resp = asyncio.run(scenario())
    assert isinstance(resp, SearchResponse)
    assert resp.query == "python httpx"  # server echo wins
    assert resp.answer == "hi"
    assert resp.ai_generated is True
    assert captured[0].headers["Authorization"] == "Bearer sp-test-key"


def test_async_search_error_mapping():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"detail": "Rate limit exceeded"}, headers={"Retry-After": "12"}
        )

    async def scenario() -> None:
        client = AsyncSearchPipe(
            api_key="sp-test-key", transport=httpx.MockTransport(handler)
        )
        try:
            await client.search("q")
        finally:
            await client.close()

    with pytest.raises(RateLimitError) as excinfo:
        asyncio.run(scenario())
    assert excinfo.value.retry_after == 12


# --- context managers --------------------------------------------------------------


def test_sync_context_manager():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=success_body())

    with make_client(handler) as client:
        assert isinstance(client, SearchPipe)
        assert client.search("q").query == "python httpx"
