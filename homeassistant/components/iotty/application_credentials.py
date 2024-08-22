"""Application credentials platform for iotty."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.application_credentials import AuthorizationServer

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

OAUTH2_AUTHORIZE = "https://auth.iotty.com/.auth/oauth2/login"
OAUTH2_TOKEN = "https://auth.iotty.com/.auth/oauth2/token"


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
