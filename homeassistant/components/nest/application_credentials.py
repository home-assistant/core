"""application_credentials platform for nest."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant

from .const import OAUTH2_TOKEN


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url="",  # Overridden in config flow as needs device access project id
        token_url=OAUTH2_TOKEN,
    )
