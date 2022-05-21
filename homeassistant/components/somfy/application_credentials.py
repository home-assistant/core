"""Application credentials platform for somfy."""
from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url="https://accounts.somfy.com/oauth/oauth/v2/auth",
        token_url="https://accounts.somfy.com/oauth/oauth/v2/token",
    )
