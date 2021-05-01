"""Tests for the Snapcast integration."""

from unittest.mock import AsyncMock


def create_mock_snapcast() -> AsyncMock:
    """Create mock snapcast connection."""
    mock_connection = AsyncMock()
    mock_connection.start = AsyncMock(return_value=None)
    return mock_connection
