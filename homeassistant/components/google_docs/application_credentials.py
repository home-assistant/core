"""Application credentials for Google Docs."""

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return Google's OAuth authorization server."""
    return AuthorizationServer(
        "https://accounts.google.com/o/oauth2/v2/auth",
        "https://oauth2.googleapis.com/token",
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return links for the application credentials form."""
    return {
        "oauth_creds_url": "https://console.cloud.google.com/apis/credentials",
        "docs_api_url": "https://console.cloud.google.com/apis/library/docs.googleapis.com",
        "redirect_uri": "https://my.home-assistant.io/redirect/oauth",
    }
