"""Application credentials platform for Viessmann ViCare."""

from PyViCare.PyViCareAbstractOAuthManager import (
    AUTHORIZE_URL,
    SCOPE_IOT,
    SCOPE_OFFLINE_ACCESS,
    TOKEN_URL,
)

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

VICARE_SCOPES = [SCOPE_IOT, SCOPE_OFFLINE_ACCESS]


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> ViCareOAuth2Implementation:
    """Return auth implementation with PKCE support."""
    return ViCareOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        AUTHORIZE_URL,
        TOKEN_URL,
    )


class ViCareOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """ViCare OAuth2 implementation with PKCE."""

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return super().extra_authorize_data | {
            "scope": " ".join(VICARE_SCOPES),
        }
