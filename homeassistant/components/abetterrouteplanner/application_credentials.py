"""Application credentials platform for A Better Routeplanner."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .oauth import AbetterrouteplannerOAuth2Implementation


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation.

    The built-in client is public, so PKCE secures the token exchange in place
    of a client secret; a user-supplied secret is still passed on.
    """
    return AbetterrouteplannerOAuth2Implementation(
        hass, auth_domain, credential.client_id, credential.client_secret
    )
