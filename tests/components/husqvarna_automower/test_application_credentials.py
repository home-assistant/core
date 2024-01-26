"""Tests for application credentials module."""
from unittest.mock import MagicMock, patch

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.components.husqvarna_automower.application_credentials import (
    async_get_authorization_server,
)
from homeassistant.core import HomeAssistant


async def test_application_credentials(hass: HomeAssistant) -> None:
    """Test application credentials."""

    with patch(
        "homeassistant.components.husqvarna_automower.application_credentials.AuthorizationServer",
        MagicMock(spec=AuthorizationServer),
    ) as mock_auth_server:
        await async_get_authorization_server(hass)
        mock_auth_server.assert_called_once()
