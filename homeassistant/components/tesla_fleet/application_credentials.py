"""application_credentials platform the Tesla Fleet integration."""

import base64
import hashlib
import logging
import secrets
from typing import Any

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DOMAIN, SCOPES


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation."""
    return TeslaOAuth2Implementation(
        hass,
        DOMAIN,
    )


class TeslaOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Tesla Fleet API Open Source Oauth2 implementation."""

    _name = "Tesla Fleet API"

    def __init__(self, hass: HomeAssistant, domain: str) -> None:
        """Initialize local auth implementation."""
        self.hass = hass
        self._domain = domain

        # Setup PKCE
        self.code_verifier = secrets.token_urlsafe(32)
        hashed_verifier = hashlib.sha256(self.code_verifier.encode()).digest()
        self.code_challenge = (
            base64.urlsafe_b64encode(hashed_verifier).decode().replace("=", "")
        )
        super().__init__(
            hass,
            domain,
            "71b813eb-4a2e-483a-b831-4dec5cb9bf0d",
            "",  # Implementation has no client secret
            "https://auth.tesla.com/oauth2/v3/authorize",
            "https://auth.tesla.com/oauth2/v3/token",
        )

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(SCOPES),
            "code_challenge": self.code_challenge,
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": self.code_verifier,  # PKCE verifier
            }
        )
