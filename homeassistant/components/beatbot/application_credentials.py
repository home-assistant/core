"""Application credentials platform for Beatbot."""

from typing import override

from beatbot_cloud.const import OAUTH2_AUTHORIZE_URL, OAUTH2_SCOPE, OAUTH2_TOKEN_URL

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> LocalOAuth2ImplementationWithPkce:
    """Return the Beatbot OAuth implementation."""
    return BeatbotOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        OAUTH2_AUTHORIZE_URL,
        OAUTH2_TOKEN_URL,
        credential.client_secret,
    )


class BeatbotOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Beatbot OAuth2 implementation with PKCE."""

    @property
    @override
    def extra_authorize_data(self) -> dict[str, str]:
        """Return extra authorize data."""
        return super().extra_authorize_data | {"scope": OAUTH2_SCOPE}
