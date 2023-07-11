"""application_credentials platform for Withings."""

from withings_api import AbstractWithingsApi, WithingsAuth

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .common import WithingsLocalOAuth2Implementation
from .const import DOMAIN


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation."""
    return WithingsLocalOAuth2Implementation(
        hass,
        DOMAIN,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url=f"{WithingsAuth.URL}/oauth2_user/authorize2",
            token_url=f"{AbstractWithingsApi.URL}/v2/oauth2",
        ),
    )
