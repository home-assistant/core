"""Application credentials platform for Tibber."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

AUTHORIZE_URL = "https://thewall.tibber.com/connect/authorize"
TOKEN_URL = "https://thewall.tibber.com/connect/token"


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server for Tibber Data API."""
    return AuthorizationServer(
        authorize_url=AUTHORIZE_URL,
        token_url=TOKEN_URL,
    )
