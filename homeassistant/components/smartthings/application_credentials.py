"""Application credentials platform for SmartThings."""

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .const import SMARTTHINGS_API_URL, SMARTTHINGS_AUTH_URL


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return auth implementation."""
    return SmartThingsOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url=SMARTTHINGS_API_URL + "/oauth/authorize",
            token_url=SMARTTHINGS_AUTH_URL + "/oauth/token",
        ),
    )


class SmartThingsOAuth2Implementation(AuthImplementation):
    """Oauth2 implementation that only uses the external url."""

    token_auth_method = "client_secret_basic"
