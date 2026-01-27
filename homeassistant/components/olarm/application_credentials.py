"""Application credentials platform for the Olarm integration."""

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    """Return authorization server."""
    return AuthorizationServer(
        authorize_url=OAUTH2_AUTHORIZE,
        token_url=OAUTH2_TOKEN,
    )


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return a custom auth implementation for public client with PKCE."""
    return config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce(
        hass,
        auth_domain,
        credential.client_id,
        OAUTH2_AUTHORIZE,
        OAUTH2_TOKEN,
        client_secret=credential.client_secret,  # Empty string for public client
    )
