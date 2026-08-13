"""Application credentials for SpaceXAI."""

from typing import override

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import AUTHORIZE_URL, OAUTH_SCOPES, TOKEN_URL


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> SpaceXAIOAuth2Implementation:
    """Return the SpaceXAI OAuth implementation."""
    return SpaceXAIOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        AUTHORIZE_URL,
        TOKEN_URL,
        credential.client_secret,
    )


class SpaceXAIOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Authorization Code + PKCE implementation for SpaceXAI."""

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        """Add least-privilege subscription access scopes."""
        return super().extra_authorize_data | {
            "scope": " ".join(OAUTH_SCOPES),
        }
