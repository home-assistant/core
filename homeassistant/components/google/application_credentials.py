"""application_credentials platform for nest."""

import oauth2client

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .api import DeviceAuth

AUTHORIZATION_SERVER = AuthorizationServer(
    oauth2client.GOOGLE_AUTH_URI, oauth2client.GOOGLE_TOKEN_URI
)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation."""
    return DeviceAuth(hass, auth_domain, credential, AUTHORIZATION_SERVER)
