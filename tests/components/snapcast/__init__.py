"""Tests for the Snapcast integration."""

from unittest.mock import AsyncMock, MagicMock


def create_mock_snapcast() -> AsyncMock:
    """Create mock snapcast connection."""
    mock_connection = AsyncMock()
    mock_connection.start = AsyncMock(return_value=None)
    mock_connection.set_on_update_callback = MagicMock(return_value=None)
    mock_connection.set_on_connect_callback = MagicMock(return_value=None)
    mock_connection.set_on_disconnect_callback = MagicMock(return_value=None)
    mock_connection.set_new_client_callback = MagicMock(return_value=None)
    return mock_connection
