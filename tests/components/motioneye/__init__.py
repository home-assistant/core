"""Tests for the motionEye integration."""

from unittest.mock import AsyncMock


def create_mock_motioneye_client() -> AsyncMock:
    """Create mock motionEye client."""
    mock_client = AsyncMock()
    mock_client.async_client_login = AsyncMock(return_value={})
    return mock_client
