"""OAuth2 implementation for A Better Routeplanner."""

from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN


class AbetterrouteplannerOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """OAuth2 implementation for A Better Routeplanner."""

    def __init__(
        self, hass: HomeAssistant, auth_domain: str, client_id: str, client_secret: str
    ) -> None:
        """Initialize the OAuth2 implementation."""
        super().__init__(
            hass,
            domain=auth_domain,
            client_id=client_id,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
            client_secret=client_secret,
        )

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "A Better Routeplanner"
