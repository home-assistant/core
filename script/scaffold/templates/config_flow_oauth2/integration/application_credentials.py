"""application_credentials platform the NEW_NAME integration."""

from spencerassistant.components.application_credentials import AuthorizationServer
from spencerassistant.core import spencerAssistant

# TODO Update with your own urls
OAUTH2_AUTHORIZE = "https://www.example.com/auth/authorize"
OAUTH2_TOKEN = "https://www.example.com/auth/token"


async def async_get_authorization_server(hass: spencerAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )
