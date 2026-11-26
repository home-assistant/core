"""Application credentials platform for the Volvo integration."""

from typing import override

from volvocarsapi.auth import get_volvoid_server

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> VolvoOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    return VolvoOAuth2Implementation(hass, auth_domain, credential)


class VolvoOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """Volvo oauth2 implementation."""

    def __init__(
        self, hass: HomeAssistant, auth_domain: str, credential: ClientCredential
    ) -> None:
        """Initialize Volvo oauth2 implementation."""
        server = get_volvoid_server(credential.client_id)
        super().__init__(
            hass,
            auth_domain,
            credential.client_id,
            server.authorize_url,
            server.token_url,
            credential.client_secret,
        )
        self._name = credential.name
        self.token_auth_method = (
            "client_secret_post" if server.legacy else "client_secret_basic"
        )

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return self._name or self.client_id
