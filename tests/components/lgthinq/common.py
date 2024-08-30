"""Test the helper method for writing tests."""

from unittest.mock import MagicMock


def mock_thinq_api_response(
    *,
    status: int = 400,
    body: dict | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> MagicMock:
    """Create a mock thinq api response."""
    response = MagicMock()
    response.status = status
    response.body = body
    response.error_code = error_code
    response.error_message = error_message
    return response
