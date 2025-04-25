"""Derived class for KEM API integration with Home Assistant."""

from __future__ import annotations

import contextlib
import logging

from aiohttp import ClientSession
from aiokem import AioKem, AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_REFRESH_TOKEN

_LOGGER = logging.getLogger(__name__)


class HAAioKem(AioKem):
    """Custom AioKem class to handle refresh token updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        session: ClientSession,
    ) -> None:
        """Initialize the HAAioKem class."""
        self.config_entry = config_entry
        self.hass = hass
        super().__init__(session=session)

    async def on_refresh_token_update(self, refresh_token: str):
        """Handle refresh token update."""
        _LOGGER.debug("Saving refresh token")
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={**self.config_entry.data, CONF_REFRESH_TOKEN: refresh_token},
        )
        return await super().on_refresh_token_update(refresh_token)

    async def login(self):
        """Login to the KEM API."""

        # Authenticate using the refresh token if available
        if refresh_token := self.config_entry.data.get(CONF_REFRESH_TOKEN):
            with contextlib.suppress(AuthenticationError):
                await self.authenticate_with_refresh_token(refresh_token)
                return

        # If refresh token is not available or authentication fails, use username and password
        await self.authenticate(
            self.config_entry.data[CONF_USERNAME], self.config_entry.data[CONF_PASSWORD]
        )
