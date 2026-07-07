"""Application credentials platform for Overkiz (Rexel)."""

from typing import override

from pyoverkiz.const import (
    REXEL_OAUTH_AUTHORIZE_URL,
    REXEL_OAUTH_POLICY,
    REXEL_OAUTH_SCOPE,
    REXEL_OAUTH_TOKEN_URL,
)

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> LocalOAuth2ImplementationWithPkce:
    """Return auth implementation for Rexel (Azure AD B2C with PKCE)."""
    return OverkizOAuth2Implementation(
        hass,
        auth_domain,
        credential.client_id,
        REXEL_OAUTH_AUTHORIZE_URL,
        REXEL_OAUTH_TOKEN_URL,
    )


class OverkizOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Overkiz (Rexel) OAuth2 implementation with PKCE."""

    @property
    @override
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url.

        Azure AD B2C requires the policy (user flow) as the ``p`` query
        parameter. It must be added here rather than baked into the authorize
        URL, because the OAuth2 helper rebuilds the query string and would
        otherwise drop it.
        """
        return super().extra_authorize_data | {
            "scope": REXEL_OAUTH_SCOPE,
            "p": REXEL_OAUTH_POLICY,
        }
