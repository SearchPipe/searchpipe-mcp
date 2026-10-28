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
from .models import (
    AnswerAudit,
    ResultEvidence,
    SearchResponse,
    SearchResult,
    StatementAudit,
    StatementCitation,
    VerifyEvidence,
    VerifyResponse,
)

__version__ = "2.0.0"

__all__ = [
    "SearchPipe",
    "AsyncSearchPipe",
    "__version__",
    # models
    "SearchResponse",
    "SearchResult",
    "VerifyResponse",
    "VerifyEvidence",
    "AnswerAudit",
    "StatementAudit",
    "StatementCitation",
    "ResultEvidence",
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
