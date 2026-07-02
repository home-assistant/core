"""OAuth2 implementation for A Better Routeplanner.

ABRP's identity provider is a public OIDC client
(``token_endpoint_auth_methods_supported`` includes ``none``), so this
integration does not use the Application Credentials platform — the
``client_id`` is built in and PKCE secures the token exchange instead of a
client secret.
"""

from typing import Any, override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    LocalOAuth2ImplementationWithPkce,
)

from .const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_CLIENT_ID,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
)


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

    @property
    @override
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data appended to the authorize URL."""
        return {"scope": " ".join(OAUTH2_SCOPES), **super().extra_authorize_data}
