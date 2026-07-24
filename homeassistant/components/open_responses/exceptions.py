"""Exceptions raised by the Open Responses integration client."""

from typing import Any


class OpenResponsesError(Exception):
    """Base exception for Open Responses client failures."""


class APIStatusError(OpenResponsesError):
    """Raised when the API returns an unsuccessful HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Any | None = None,
    ) -> None:
        """Initialize an API status error."""
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class AuthenticationError(APIStatusError):
    """Raised when credentials are missing or rejected."""


class RateLimitError(APIStatusError):
    """Raised when the API rejects a request due to rate limits."""


class BadRequestError(APIStatusError):
    """Raised when the request body is invalid."""


class ModelError(APIStatusError):
    """Raised when the requested model is missing or unavailable."""


class APIConnectionError(OpenResponsesError):
    """Raised when the API cannot be reached."""
