"""Application credentials platform for SmartThings."""

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .app_ledger import async_get_app_ledger
from .const import DOMAIN, SMARTTHINGS_API_URL, SMARTTHINGS_AUTH_URL


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return auth implementation."""
    ledger = await async_get_app_ledger(hass)
    # Entries set up with other credentials reference the legacy DOMAIN key.
    if not ledger.is_provisioned_auth_domain(auth_domain):
        auth_domain = DOMAIN
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
