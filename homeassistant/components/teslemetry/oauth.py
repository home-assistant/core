"""Provide oauth implementations for the Teslemetry integration."""

import base64
import hashlib
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import AUTHORIZE_URL, CLIENT_ID, DOMAIN, TOKEN_URL


class TeslemetryImplementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Tesla Fleet API open source Oauth2 implementation."""

    code_verifier: str
    code_challenge: str

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
            CLIENT_ID,
            "",
            AUTHORIZE_URL,
            TOKEN_URL,
        )

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Teslemetry OAuth2"

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "code_challenge": self.code_challenge,  # PKCE
        }

    @property
    def extra_token_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the token request."""
        # print("extra_token_data", self.hass.config.location_name)
        return {
            "name": self.hass.config.location_name,
        }

    @property
    def extra_token_resolve_data(self) -> dict:
        """Extra data that needs to be appended to the token resolve request."""
        # print("extra_token_resolve_data", self.hass.config.location_name)
        return {
            "name": self.hass.config.location_name,
        }

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return await self._token_request(
            {
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": external_data["code"],
                "redirect_uri": external_data["state"]["redirect_uri"],
                "code_verifier": self.code_verifier,  # PKCE
            }
        )
