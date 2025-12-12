"""Provide oauth implementations for the Teslemetry integration."""

from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import AUTHORIZE_URL, CLIENT_ID, DOMAIN, TOKEN_URL, TOKEN_URLS


class TeslemetryImplementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    """Tesla Fleet API OAuth2 implementation with region support."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize OAuth2 implementation."""
        # Setup PKCE
        self.code_verifier = secrets.token_urlsafe(32)
        hashed_verifier = hashlib.sha256(self.code_verifier.encode()).digest()
        self.code_challenge = (
            base64.urlsafe_b64encode(hashed_verifier).decode().replace("=", "")
        )

        # Use placeholder token URL - will be updated based on region
        super().__init__(
            hass,
            DOMAIN,
            CLIENT_ID,
            "",
            AUTHORIZE_URL,
            TOKEN_URL,
        )

        # Store region for token requests
        self._region: str | None = None

    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Teslemetry OAuth2"

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {
            "code_challenge": self.code_challenge,
        }

    @property
    def extra_token_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the token request."""
        return {
            "name": self.hass.config.location_name,
        }

    @property
    def extra_token_resolve_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the token resolve request."""
        return {
            "name": self.hass.config.location_name,
            "code_verifier": self.code_verifier,
        }

    def set_region(self, region: str) -> None:
        """Set the region and update token URL."""
        if region not in TOKEN_URLS:
            raise ValueError(
                f"Invalid region '{region}'. Must be one of: {', '.join(TOKEN_URLS.keys())}"
            )
        self.token_url = TOKEN_URLS[region]
