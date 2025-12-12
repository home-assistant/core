"""Provide oauth implementations for the Teslemetry integration."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import AUTHORIZE_URL, CLIENT_ID, DOMAIN, TOKEN_URL


class TeslemetryImplementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Teslemetry OAuth2 implementation."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize OAuth2 implementation."""
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
            "name": self.hass.config.location_name,
            "code_challenge": self.code_challenge,
        }

    @property
    def extra_token_resolve_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the token resolve request."""
        return {
            "name": self.hass.config.location_name,
            "code_verifier": self.code_verifier,
        }
