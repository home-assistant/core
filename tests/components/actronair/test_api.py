"""Tests for ActronAir API authentication and data fetching."""

from unittest.mock import AsyncMock

from homeassistant.components.actronair.api import AsyncConfigEntryAuth


async def test_async_get_access_token() -> None:
    """Test token retrieval from ActronAir API."""
    mock_oauth_session = AsyncMock()
    mock_oauth_session.valid_token = False
    mock_oauth_session.token = {"access_token": "test_token"}
    mock_oauth_session.async_ensure_token_valid = AsyncMock()

    auth = AsyncConfigEntryAuth(None, mock_oauth_session)
    token = await auth.async_get_access_token()

    assert token == "test_token"
    mock_oauth_session.async_ensure_token_valid.assert_called_once()
