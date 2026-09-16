"""LangChain integration for SearchPipe — AI-powered web search API.

Provides:
- ``SearchPipeRetriever`` — drop-in retriever for RAG pipelines.
- ``SearchPipeSearchResults`` — tool for agents that need structured search results.
- ``SearchPipeAnswer`` — tool that returns the LLM-synthesized answer with citations.

All components call the Tavily-style ``POST /search`` endpoint on
``https://searchpipe.tech`` (or a self-hosted instance).
"""

from langchain_searchpipe.retriever import SearchPipeRetriever
from langchain_searchpipe.tool import SearchPipeAnswer, SearchPipeSearchResults

__all__ = [
    "SearchPipeRetriever",
    "SearchPipeSearchResults",
    "SearchPipeAnswer",
    "__version__",
]

__version__ = "0.1.0"
