"""SearchPipe tools for LangChain agents."""

from __future__ import annotations

from typing import Any, Optional, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from langchain_searchpipe.client import SearchPipeClient


class _SearchPipeInput(BaseModel):
    query: str = Field(description="Search query to look up on the web.")


class SearchPipeSearchResults(BaseTool):
    """Tool that returns structured web search results from SearchPipe.

    Returns a JSON-serializable dict with ``query``, ``answer`` (optional),
    and ``results`` — a list of ``{title, url, content, score}`` dicts.
    Suitable for agents that want to inspect / cite individual sources.
    """

    name: str = "searchpipe_search"
    description: str = (
        "Search the web via SearchPipe (AI-powered search API with LLM "
        "reranking). Returns structured results with title, URL, snippet, "
        "and relevance score. Use this for current-events, factual lookups, "
        "or any question that benefits from retrieved sources."
    )
    args_schema: Type[BaseModel] = _SearchPipeInput

    api_key: Optional[str] = Field(default=None, repr=False)
    base_url: Optional[str] = Field(default=None)
    max_results: int = Field(default=5, ge=1, le=20)
    search_depth: str = Field(default="basic")
    include_answer: bool = Field(default=False)
    include_raw_content: bool = Field(default=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _client(self) -> SearchPipeClient:
        return SearchPipeClient(api_key=self.api_key, base_url=self.base_url)

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> dict[str, Any]:
        return self._client.search(
            query,
            max_results=self.max_results,
            search_depth=self.search_depth,
            include_answer=self.include_answer,
            include_raw_content=self.include_raw_content,
        )

    async def _arun(
        self,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> dict[str, Any]:
        return await self._client.asearch(
            query,
            max_results=self.max_results,
            search_depth=self.search_depth,
            include_answer=self.include_answer,
            include_raw_content=self.include_raw_content,
        )


class SearchPipeAnswer(BaseTool):
    """Tool that returns SearchPipe's LLM-synthesized answer with citations.

    Cheaper to consume for agents that just need a natural-language answer
    grounded in retrieved sources, without listing every result.
    """

    name: str = "searchpipe_answer"
    description: str = (
        "Ask SearchPipe a question and get back a concise LLM-synthesized "
        "answer grounded in live web search results. Use this when you want "
        "a direct answer rather than a list of links."
    )
    args_schema: Type[BaseModel] = _SearchPipeInput

    api_key: Optional[str] = Field(default=None, repr=False)
    base_url: Optional[str] = Field(default=None)
    max_results: int = Field(default=5, ge=1, le=20)
    search_depth: str = Field(default="basic")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _client(self) -> SearchPipeClient:
        return SearchPipeClient(api_key=self.api_key, base_url=self.base_url)

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        data = self._client.search(
            query,
            max_results=self.max_results,
            search_depth=self.search_depth,
            include_answer=True,
        )
        answer = data.get("answer") or ""
        if not answer:
            # Fallback: concatenate snippets so the agent still gets signal.
            snippets = [r.get("content", "") for r in data.get("results", [])]
            answer = "\n\n".join(s for s in snippets if s)
        return answer

    async def _arun(
        self,
        query: str,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        data = await self._client.asearch(
            query,
            max_results=self.max_results,
            search_depth=self.search_depth,
            include_answer=True,
        )
        answer = data.get("answer") or ""
        if not answer:
            snippets = [r.get("content", "") for r in data.get("results", [])]
            answer = "\n\n".join(s for s in snippets if s)
        return answer
