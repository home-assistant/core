"""Test application credentials for Watts integration."""

from homeassistant.components.watts.application_credentials import (
    async_get_authorization_server,
)
from homeassistant.components.watts.const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from homeassistant.core import HomeAssistant


async def test_async_get_authorization_server(hass: HomeAssistant) -> None:
    """Test getting authorization server."""
    auth_server = await async_get_authorization_server(hass)

    assert auth_server.authorize_url == OAUTH2_AUTHORIZE
    assert auth_server.token_url == OAUTH2_TOKEN
