"""Application credentials platform for Home Connect."""

from aiohomeconnect.const import (
    OAUTH2_AUTHORIZE,
    OAUTH2_AUTHORIZE_CHINA,
    OAUTH2_TOKEN,
    OAUTH2_TOKEN_CHINA,
)

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return (
        AuthorizationServer(
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        )
        if hass.config.country != "CN"
        else AuthorizationServer(
            authorize_url=OAUTH2_AUTHORIZE_CHINA,
            token_url=OAUTH2_TOKEN_CHINA,
        )
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    developer_dashboard_url = "https://developer.home-connect.com/"
    applications_url = "https://developer.home-connect.com/applications"
    register_application_url = "https://developer.home-connect.com/application/add"

    if hass.config.country == "CN":
        developer_dashboard_url = developer_dashboard_url.replace(".com", ".cn")
        applications_url = applications_url.replace(".com", ".cn")
        register_application_url = register_application_url.replace(".com", ".cn")

    return {
        "developer_dashboard_url": developer_dashboard_url,
        "applications_url": applications_url,
        "register_application_url": register_application_url,
        "redirect_url": "https://my.home-assistant.io/redirect/oauth",
    }
