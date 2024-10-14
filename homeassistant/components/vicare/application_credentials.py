"""application_credentials platform the Viessmann ViCare integration."""

from PyViCare.PyViCareOAuthManager import AUTHORIZE_URL, TOKEN_URL

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=AUTHORIZE_URL,
        token_url=TOKEN_URL,
    )
