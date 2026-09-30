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
    assert __version__ == "0.1.0"
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
