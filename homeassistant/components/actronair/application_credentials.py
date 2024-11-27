"""application_credentials platform the Actron Air integration."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

OAUTH2_AUTHORIZE = "https://nimbus.actronair.com.au/authorize"
OAUTH2_TOKEN = "https://nimbus.actronair.com.au/api/v0/oauth/token"


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
