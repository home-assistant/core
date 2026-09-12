"""OAuth2 implementation for A Better Routeplanner.

ABRP's identity provider is a public OIDC client, so this integration ships a
built-in ``client_id`` instead of using the Application Credentials platform,
and PKCE secures the token exchange in place of a client secret.
"""

from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_CLIENT_ID, OAUTH2_TOKEN


class AbetterrouteplannerOAuth2Implementation(LocalOAuth2ImplementationWithPkce):
    """OAuth2 implementation for A Better Routeplanner."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the OAuth2 implementation."""
        super().__init__(
            hass,
            domain=DOMAIN,
            client_id=OAUTH2_CLIENT_ID,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
            code_verifier_length=128,
        )

    @property
    @override
    def name(self) -> str:
        """Name of the implementation."""
        return "A Better Routeplanner"
