"""SearchPipe retriever for LangChain RAG pipelines."""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.callbacks import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field, PrivateAttr

from langchain_searchpipe.client import SearchPipeClient


class SearchPipeRetriever(BaseRetriever):
    """Retriever that fetches web search results from SearchPipe.

    Each SearchPipe result becomes a :class:`~langchain_core.documents.Document`
    with ``page_content`` set to the snippet (or full raw content when
    ``include_raw_content=True``) and metadata carrying ``title``, ``url``,
    ``score``, and the original ``query``.

    Parameters
    ----------
    api_key:
        SearchPipe API key. Falls back to ``SEARCHPIPE_API_KEY`` env var.
    base_url:
        Override for self-hosted SearchPipe instances.
    max_results:
        Number of results to return per query (1–20).
    search_depth:
        ``"basic"`` (1 credit/call) or ``"advanced"`` (2 credits/call).
    include_raw_content:
        When ``True``, fetches full page content into ``page_content``
        (slower, costs more credits).
    include_answer:
        When ``True``, asks SearchPipe to also synthesize an LLM answer.
        The answer is exposed via :attr:`last_answer` after each call.
    """

    api_key: Optional[str] = Field(default=None, repr=False)
    base_url: Optional[str] = Field(default=None)
    max_results: int = Field(default=5, ge=1, le=20)
    search_depth: str = Field(default="basic")
    include_raw_content: bool = Field(default=False)
    include_answer: bool = Field(default=False)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _last_answer: Optional[str] = PrivateAttr(default=None)

    @property
    def last_answer(self) -> Optional[str]:
        """LLM-synthesized answer from the most recent call (if requested)."""
        return self._last_answer

    @property
    def _client(self) -> SearchPipeClient:
        # Re-created per call so that env-var changes are picked up in notebooks.
        return SearchPipeClient(api_key=self.api_key, base_url=self.base_url)

    def _build_documents(self, data: dict[str, Any]) -> list[Document]:
        self._last_answer = data.get("answer")
        query = data.get("query", "")
        docs: list[Document] = []
        for r in data.get("results", []):
            content = r.get("raw_content") if self.include_raw_content else None
            if not content:
                content = r.get("content", "")
            docs.append(
                Document(
                    page_content=content or "",
                    metadata={
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "score": r.get("score", 0.0),
                        "query": query,
                    },
                )
            )
        return docs

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        data = self._client.search(
            query,
            max_results=self.max_results,
            search_depth=self.search_depth,
            include_answer=self.include_answer,
            include_raw_content=self.include_raw_content,
        )
        return self._build_documents(data)

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        data = await self._client.asearch(
            query,
            max_results=self.max_results,
            search_depth=self.search_depth,
            include_answer=self.include_answer,
            include_raw_content=self.include_raw_content,
        )
        return self._build_documents(data)
