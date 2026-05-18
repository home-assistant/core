"""Data update coordinator for the openSenseMap integration."""

import asyncio

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, LOGGER, SCAN_INTERVAL

type OpenSenseMapConfigEntry = ConfigEntry[OpenSenseMapCoordinator]


class OpenSenseMapCoordinator(DataUpdateCoordinator[None]):
    """Coordinator to manage data updates for an openSenseMap station."""

    config_entry: OpenSenseMapConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OpenSenseMapConfigEntry,
        api: OpenSenseMap,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> None:
        """Fetch latest data from the openSenseMap API."""
        try:
            async with asyncio.timeout(API_TIMEOUT):
                await self.api.get_data()
        except (OpenSenseMapError, TimeoutError) as err:
            raise UpdateFailed(
                f"Unable to fetch data from openSenseMap: {err}"
            ) from err
