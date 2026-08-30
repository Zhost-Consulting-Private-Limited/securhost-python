"""
Exceptions raised by the SecurHost client.
"""

from __future__ import annotations

from typing import Any


class SecurHostError(Exception):
    """Base class for every error this package raises."""

    @property
    def retryable(self) -> bool:
        return False


class SecurHostConnectionError(SecurHostError):
    """The transport failed before reaching the gateway."""

    @property
    def retryable(self) -> bool:
        return True


class SecurHostAPIError(SecurHostError):
    """The gateway returned an HTTP error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        code: str | None = None,
        error_type: str | None = None,
        request_id: str | None = None,
        body: Any = None,
        response: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.error_type = error_type
        self.request_id = request_id
        self.body = body
        self.response = response

    @property
    def retryable(self) -> bool:
        return self.status_code in (408, 429, 500, 502, 503, 504)

    def __repr__(self) -> str:
        parts = [f"status_code={self.status_code}"]
        if self.code:
            parts.append(f"code={self.code!r}")
        if self.error_type:
            parts.append(f"type={self.error_type!r}")
        if self.request_id:
            parts.append(f"request_id={self.request_id!r}")
        return f"{self.__class__.__name__}({super().__str__()!r}, {', '.join(parts)})"


class SecurHostAuthError(SecurHostAPIError):
    """Invalid API key or missing permissions (HTTP 401 / 403)."""

    @property
    def retryable(self) -> bool:
        return False


class SecurHostRateLimitError(SecurHostAPIError):
    """Too many requests (HTTP 429)."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        code: str | None = None,
        error_type: str | None = None,
        request_id: str | None = None,
        body: Any = None,
        response: Any = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            code=code,
            error_type=error_type,
            request_id=request_id,
            body=body,
            response=response,
        )
        self.retry_after = retry_after

    @property
    def retryable(self) -> bool:
        return True
