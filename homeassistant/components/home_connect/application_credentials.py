"""Application credentials platform for Home Connect."""

from aiohomeconnect.const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "developer_dashboard_url": "https://developer.home-connect.com/",
        "applications_url": "https://developer.home-connect.com/applications",
        "register_application_url": "https://developer.home-connect.com/application/add",
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
    }
