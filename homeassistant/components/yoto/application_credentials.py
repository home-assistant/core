"""Application credentials platform for the Yoto integration."""

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import YOTO_AUDIENCE, YOTO_SCOPES

AUTHORIZE_URL = "https://login.yotoplay.com/authorize"
TOKEN_URL = "https://login.yotoplay.com/oauth/token"


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> YotoOAuth2Implementation:
    """Return a Yoto OAuth2 implementation backed by the user's credential."""
    return YotoOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        AUTHORIZE_URL,
        TOKEN_URL,
        credential.client_secret,
    )


class YotoOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Yoto OAuth2 implementation with PKCE, audience and scopes."""

    @property
    def extra_authorize_data(self) -> dict:
        """Append Yoto's audience and scopes to every authorize URL."""
        return super().extra_authorize_data | {
            "audience": YOTO_AUDIENCE,
            "scope": " ".join(YOTO_SCOPES),
        }
