"""Test authentication for Watts Vision+ integration."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.watts.auth import ConfigEntryAuth
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow


async def test_config_entry_auth_initialization(hass: HomeAssistant) -> None:
    """Test ConfigEntryAuth initialization."""
    mock_session = MagicMock(spec=config_entry_oauth2_flow.OAuth2Session)
    mock_session.token = {
        "access_token": "test_token",
        "refresh_token": "refresh_token",
    }

    auth = ConfigEntryAuth(hass, mock_session)

    assert auth.hass == hass
    assert auth.session == mock_session
    assert auth.token == mock_session.token


async def test_refresh_tokens(hass: HomeAssistant) -> None:
    """Test token refresh."""
    mock_session = MagicMock(spec=config_entry_oauth2_flow.OAuth2Session)
    mock_session.token = {
        "access_token": "new_access_token",
        "refresh_token": "refresh_token",
    }
    mock_session.async_ensure_token_valid = AsyncMock()

    auth = ConfigEntryAuth(hass, mock_session)

    result = await auth.refresh_tokens()

    assert result == "new_access_token"
    mock_session.async_ensure_token_valid.assert_called_once()
