"""Application credentials platform for neato."""

from pybotvac import Neato

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from . import api


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    vendor = Neato()
    return api.NeatoImplementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url=vendor.auth_endpoint,
            token_url=vendor.token_endpoint,
        ),
    )
