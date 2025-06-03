"""Application credentials platform for LaMetric."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url="https://developer.lametric.com/api/v2/oauth2/authorize",
        token_url="https://developer.lametric.com/api/v2/oauth2/token",
    )
