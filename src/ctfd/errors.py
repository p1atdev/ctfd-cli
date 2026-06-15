from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CtfdError(Exception):
    """Base exception for the CTFd client."""


class CtfdConfigError(CtfdError):
    """Raised when client configuration is missing or invalid."""


class CtfdConnectionError(CtfdError):
    """Raised when the CTFd server cannot be reached."""


class CtfdTimeoutError(CtfdConnectionError):
    """Raised when a request to the CTFd server times out."""


class CtfdResponseError(CtfdError):
    """Raised when the server returns an invalid API response."""


class CtfdHTTPError(CtfdError):
    """Raised for an unsuccessful HTTP response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        errors: Mapping[str, Any] | list[Any] | str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors


class CtfdAPIError(CtfdHTTPError):
    """Raised when CTFd returns a structured API error."""


class CtfdAuthenticationError(CtfdAPIError):
    """Raised when the API token is missing or rejected."""


class CtfdPermissionError(CtfdAPIError):
    """Raised when the authenticated user cannot perform an operation."""


class CtfdNotFoundError(CtfdAPIError):
    """Raised when an API resource does not exist or is hidden."""


class CtfdRateLimitError(CtfdAPIError):
    """Raised when the server rejects a request due to rate limiting."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 429,
        errors: Mapping[str, Any] | list[Any] | str | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, errors=errors)
        self.retry_after = retry_after
