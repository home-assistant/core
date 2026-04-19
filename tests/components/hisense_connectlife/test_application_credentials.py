"""Tests for the Hisense ConnectLife application credentials platform."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.components.hisense_connectlife.application_credentials import (
    async_get_authorization_server,
)
from homeassistant.components.hisense_connectlife.const import (
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant


async def test_async_get_authorization_server(hass: HomeAssistant) -> None:
    """Test authorization server configuration."""
    server = await async_get_authorization_server(hass)

    assert isinstance(server, AuthorizationServer)
    assert server.authorize_url == OAUTH2_AUTHORIZE
    assert server.token_url == OAUTH2_TOKEN
