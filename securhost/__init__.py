"""
The SecurHost AI Python SDK.

Reads X-SecurHost-* headers for real-time cost, model routing, and savings telemetry.
"""

from __future__ import annotations

from securhost.aio import AsyncSecurHostClient
from securhost.client import SecurHostClient
from securhost.errors import (
    SecurHostAPIError,
    SecurHostAuthError,
    SecurHostConnectionError,
    SecurHostError,
    SecurHostRateLimitError,
)
from securhost.types import ChatResponse, Cost, EmbeddingResponse, Usage
from securhost.webhooks import verify_signature

__version__ = "0.1.0"

__all__ = [
    "AsyncSecurHostClient",
    "ChatResponse",
    "Cost",
    "EmbeddingResponse",
    "SecurHostAPIError",
    "SecurHostAuthError",
    "SecurHostClient",
    "SecurHostConnectionError",
    "SecurHostError",
    "SecurHostRateLimitError",
    "Usage",
    "__version__",
    "verify_signature",
]
