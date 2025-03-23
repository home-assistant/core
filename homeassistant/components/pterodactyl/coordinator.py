"""Data update coordinator of the Pterodactyl integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PterodactylAPI,
    PterodactylConfigurationError,
    PterodactylConnectionError,
    PterodactylData,
    PterodactylNotInitializedError,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

type PterodactylConfigEntry = ConfigEntry[PterodactylCoordinator]


class PterodactylCoordinator(DataUpdateCoordinator[list[PterodactylData]]):
    """Pterodactyl data update coordinator."""

    config_entry: PterodactylConfigEntry
    api: PterodactylAPI

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PterodactylConfigEntry,
    ) -> None:
        """Initialize coordinator instance."""

        super().__init__(
            hass=hass,
            name=config_entry.data[CONF_HOST],
            config_entry=config_entry,
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_setup(self) -> None:
        """Set up the Pterodactyl data coordinator."""
        try:
            self.api = PterodactylAPI(
                hass=self.hass,
                host=self.config_entry.data[CONF_HOST],
                api_key=self.config_entry.data[CONF_API_KEY],
            )
            await self.api.async_init()
        except PterodactylConfigurationError as error:
            raise ConfigEntryNotReady(error) from error

    async def _async_update_data(self) -> list[PterodactylData]:
        """Get updated data from the Pterodactyl server."""
        try:
            return await self.api.async_get_data_list()
        except (PterodactylNotInitializedError, PterodactylConnectionError) as error:
            raise UpdateFailed(error) from error
