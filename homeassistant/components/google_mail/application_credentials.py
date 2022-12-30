"""application_credentials platform for Google Mail."""

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
import oauth2client

from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import DATA_SESSION

AUTHORIZATION_SERVER = AuthorizationServer(
    oauth2client.GOOGLE_AUTH_URI, oauth2client.GOOGLE_TOKEN_URI
)


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        oauth2client.GOOGLE_AUTH_URI,
        oauth2client.GOOGLE_TOKEN_URI,
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "oauth_consent_url": "https://console.cloud.google.com/apis/credentials/consent",
        "more_info_url": "https://www.home-assistant.io/integrations/google_mail/",
        "oauth_creds_url": "https://console.cloud.google.com/apis/credentials",
    }


async def get_oauth_service(data: dict[str, Any]) -> Resource:
    """Get valid service with latest access token."""
    session: OAuth2Session = data[DATA_SESSION]
    await session.async_ensure_token_valid()
    credentials = Credentials(data[CONF_TOKEN][CONF_ACCESS_TOKEN])
    return build("gmail", "v1", credentials=credentials)
