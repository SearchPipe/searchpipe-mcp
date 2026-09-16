"""Unit tests for langchain-searchpipe (no real network calls)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx

from langchain_searchpipe import (
    SearchPipeAnswer,
    SearchPipeRetriever,
    SearchPipeSearchResults,
)
from langchain_searchpipe.client import SearchPipeAPIError

API_KEY = "sp-test-key-123"
BASE_URL = "https://searchpipe.tech"

FAKE_RESPONSE: dict[str, Any] = {
    "query": "langchain",
    "answer": "LangChain is a framework for building LLM applications.",
    "ai_generated": True,
    "results": [
        {
            "url": "https://example.com/1",
            "title": "Result One",
            "content": "snippet one",
            "score": 0.95,
            "raw_content": None,
        },
        {
            "url": "https://example.com/2",
            "title": "Result Two",
            "content": "snippet two",
            "score": 0.85,
            "raw_content": None,
        },
    ],
}


@pytest.fixture(autouse=True)
def _env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SEARCHPIPE_API_KEY", API_KEY)


# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------


@respx.mock
def test_retriever_invoke_returns_documents() -> None:
    route = respx.post(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    retriever = SearchPipeRetriever()
    docs = retriever.invoke("langchain")

    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent["query"] == "langchain"
    assert sent["max_results"] == 5

    assert len(docs) == 2
    assert docs[0].page_content == "snippet one"
    assert docs[0].metadata["url"] == "https://example.com/1"
    assert docs[0].metadata["title"] == "Result One"
    assert docs[0].metadata["score"] == 0.95
    assert docs[0].metadata["query"] == "langchain"


@respx.mock
@pytest.mark.asyncio
async def test_retriever_ainvoke_returns_documents() -> None:
    route = respx.post(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    retriever = SearchPipeRetriever()
    docs = await retriever.ainvoke("langchain")
    assert route.called
    assert len(docs) == 2


@respx.mock
def test_retriever_include_raw_content_uses_raw() -> None:
    body = dict(FAKE_RESPONSE)
    body["results"] = [
        {**FAKE_RESPONSE["results"][0], "raw_content": "FULL PAGE TEXT"},
    ]
    respx.post(f"{BASE_URL}/search").mock(return_value=httpx.Response(200, json=body))
    retriever = SearchPipeRetriever(include_raw_content=True)
    docs = retriever.invoke("langchain")
    assert docs[0].page_content == "FULL PAGE TEXT"


@respx.mock
def test_retriever_api_error_raises() -> None:
    respx.post(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(402, text="balance is insufficient")
    )
    retriever = SearchPipeRetriever()
    with pytest.raises(SearchPipeAPIError) as exc_info:
        retriever.invoke("langchain")
    assert exc_info.value.status_code == 402


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@respx.mock
def test_search_results_tool_returns_payload() -> None:
    route = respx.post(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    tool = SearchPipeSearchResults(include_answer=True)
    out = tool.invoke({"query": "langchain"})
    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent["include_answer"] is True
    assert out["answer"] == FAKE_RESPONSE["answer"]
    assert len(out["results"]) == 2


@respx.mock
@pytest.mark.asyncio
async def test_search_results_tool_async() -> None:
    route = respx.post(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    tool = SearchPipeSearchResults()
    out = await tool.ainvoke({"query": "langchain"})
    assert route.called
    assert out["query"] == "langchain"


@respx.mock
def test_answer_tool_returns_answer() -> None:
    respx.post(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    tool = SearchPipeAnswer()
    out = tool.invoke({"query": "what is langchain"})
    assert out == FAKE_RESPONSE["answer"]


@respx.mock
def test_answer_tool_falls_back_to_snippets() -> None:
    body = dict(FAKE_RESPONSE)
    body["answer"] = None
    respx.post(f"{BASE_URL}/search").mock(return_value=httpx.Response(200, json=body))
    tool = SearchPipeAnswer()
    out = tool.invoke({"query": "langchain"})
    assert "snippet one" in out
    assert "snippet two" in out


# ---------------------------------------------------------------------------
# Client auth / config
# ---------------------------------------------------------------------------


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SEARCHPIPE_API_KEY", raising=False)
    retriever = SearchPipeRetriever(api_key=None)
    with pytest.raises(Exception) as exc_info:
        retriever.invoke("x")
    assert "SEARCHPIPE_API_KEY" in str(exc_info.value) or "api_key" in str(exc_info.value)


@respx.mock
def test_custom_base_url() -> None:
    route = respx.post("https://selfhosted.example.com/search").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    retriever = SearchPipeRetriever(base_url="https://selfhosted.example.com")
    docs = retriever.invoke("q")
    assert route.called
    assert len(docs) == 2


@respx.mock
def test_bearer_header_sent() -> None:
    route = respx.post(f"{BASE_URL}/search").mock(
        return_value=httpx.Response(200, json=FAKE_RESPONSE)
    )
    SearchPipeRetriever().invoke("q")
    auth = route.calls[0].request.headers["Authorization"]
    assert auth == f"Bearer {API_KEY}"
