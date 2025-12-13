"""Provide oauth implementations for the Teslemetry integration."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .const import AUTHORIZE_URL, CLIENT_ID, DOMAIN, TOKEN_URL


class TeslemetryImplementation(
    config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce
):
    """Teslemetry OAuth2 implementation."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize OAuth2 implementation."""

        super().__init__(
            hass,
            DOMAIN,
            CLIENT_ID,
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
        data: dict = {
            "name": self.hass.config.location_name,
        }
        return data

    @property
    def extra_token_resolve_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the token resolve request."""
        data: dict = {
            "name": self.hass.config.location_name,
        }
        data.update(super().extra_token_resolve_data)
        return data
