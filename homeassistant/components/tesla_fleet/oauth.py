"""Provide oauth implementations for the Tesla Fleet integration."""

import base64
import hashlib
import secrets
from typing import Any

from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant

from .const import AUTHORIZE_URL, CLIENT_ID, DOMAIN, SCOPES, TOKEN_URL

AUTH_SERVER = AuthorizationServer(AUTHORIZE_URL, TOKEN_URL)


class TeslaSystemImplementation(AuthImplementation):
    """Tesla Fleet API open source Oauth2 implementation."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize open source Oauth2 implementation."""

        # Setup PKCE
        self.code_verifier = secrets.token_urlsafe(32)
        hashed_verifier = hashlib.sha256(self.code_verifier.encode()).digest()
        self.code_challenge = (
            base64.urlsafe_b64encode(hashed_verifier).decode().replace("=", "")
        )
        super().__init__(
            hass,
            DOMAIN,
            ClientCredential(CLIENT_ID, "", "Built-in open source client ID"),
            AUTH_SERVER,
        )

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "scope": " ".join(SCOPES),
            "code_challenge": self.code_challenge,  # PKCE
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": self.code_verifier,  # PKCE
            }
        )


class TeslaUserImplementation(AuthImplementation):
    """Tesla Fleet API user Oauth2 implementation."""

    def __init__(
        self, hass: HomeAssistant, auth_domain: str, credential: ClientCredential
    ) -> None:
        """Initialize user Oauth2 implementation."""

        super().__init__(
            hass,
            auth_domain,
            credential,
            AUTH_SERVER,
        )

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(SCOPES)}
