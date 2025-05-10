"""Application credentials platform for the Volvo integration."""

from volvocarsapi.auth import AUTHORIZE_URL, TOKEN_URL

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    LocalOAuth2ImplementationWithPkce,
)

from .const import SCOPES


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    return VolvoOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        authorization_server=AuthorizationServer(
            authorize_url=AUTHORIZE_URL,
            token_url=TOKEN_URL,
        ),
    )


class VolvoOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Volvo oauth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
        auth_domain: str,
        credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            auth_domain,
            credential.client_id,
            authorization_server.authorize_url,
            authorization_server.token_url,
            credential.client_secret,
        )

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return super().extra_authorize_data | {
            "scope": " ".join(SCOPES),
        }
