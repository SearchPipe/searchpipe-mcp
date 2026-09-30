"""SearchPipe — Official Python SDK for the SearchPipe web search API."""

from __future__ import annotations

from .client import AsyncSearchPipe, SearchPipe
from .exceptions import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    EmailNotVerifiedError,
    InsufficientCreditsError,
    RateLimitError,
    SearchPipeError,
    SearchPipeServerError,
    ValidationError,
)
from .models import SearchResponse, SearchResult

__version__ = "0.1.0"

__all__ = [
    "SearchPipe",
    "AsyncSearchPipe",
    "__version__",
    # models
    "SearchResponse",
    "SearchResult",
    # exceptions
    "SearchPipeError",
    "APIConnectionError",
    "APIStatusError",
    "AuthenticationError",
    "EmailNotVerifiedError",
    "InsufficientCreditsError",
    "RateLimitError",
    "BadRequestError",
    "ValidationError",
    "SearchPipeServerError",
]
