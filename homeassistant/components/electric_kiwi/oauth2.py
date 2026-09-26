"""OAuth2 implementations for Toon."""

from typing import Any, override

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant

from .const import SCOPE_VALUES


class ElectricKiwiLocalOAuth2Implementation(AuthImplementation):
    """Local OAuth2 implementation for Electric Kiwi."""

    token_auth_method = "client_secret_basic"

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        client_credential: ClientCredential,
        authorization_server: AuthorizationServer,
    ) -> None:
        """Set up Electric Kiwi oauth."""
        super().__init__(
            hass=hass,
            auth_domain=domain,
            credential=client_credential,
            authorization_server=authorization_server,
        )

        self._name = client_credential.name

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": SCOPE_VALUES}
