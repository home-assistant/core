"""Coordinator to update data from Aquacell API."""

import asyncio
from datetime import timedelta
import logging

from aioaquacell import (
    AquacellApi,
    AquacellApiException,
    AuthenticationFailed,
    Softener,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_REFRESH_TOKEN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class AquacellCoordinator(DataUpdateCoordinator[dict[str, Softener]]):
    """My aquacell coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, aquacell_api: AquacellApi) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Aquacell Coordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

        self.refresh_token = self.config_entry.data[CONF_REFRESH_TOKEN]
        self.email = self.config_entry.data[CONF_EMAIL]
        self.password = self.config_entry.data[CONF_PASSWORD]
        self.aquacell_api = aquacell_api

    async def _async_update_data(self) -> dict[str, Softener]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        async with asyncio.timeout(10):
            _LOGGER.debug("Logging in using: %s", self.refresh_token)

            try:
                await self.aquacell_api.authenticate_refresh(self.refresh_token)
            except AuthenticationFailed as err:
                _LOGGER.debug(
                    "Authentication using refresh token failed due to: %s", err
                )
                _LOGGER.debug("Attempting to renew refresh token")
                refresh_token = await self.aquacell_api.authenticate(
                    self.email, self.password
                )
                self.refresh_token = refresh_token
                self._update_config_entry_refresh_token()

            _LOGGER.debug("Logged in, new token: %s", self.aquacell_api.id_token)
        try:
            softeners = await self.aquacell_api.get_all_softeners()
        except AuthenticationFailed as err:
            raise ConfigEntryError from err
        except AquacellApiException as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        return {softener.dsn: softener for softener in softeners}

    def _update_config_entry_refresh_token(self) -> None:
        """Update or delete the refresh_token in the Config Entry."""
        data = {
            **self.config_entry.data,
            CONF_REFRESH_TOKEN: self.refresh_token,
        }

        self.hass.config_entries.async_update_entry(self.config_entry, data=data)
