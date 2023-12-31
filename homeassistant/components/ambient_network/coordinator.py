"""DataUpdateCoordinator for the Ambient Weather Network integration."""

from __future__ import annotations

from typing import Any

from aioambient import OpenAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ENTITY_MAC_ADDRESS, ENTITY_STATIONS, LOGGER, SCAN_INTERVAL


class AmbientNetworkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The Ambient Network Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api: OpenAPI) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the Ambient Network."""

        station_data: dict[str, Any] = {}
        for station in self.config_entry.data[ENTITY_STATIONS]:
            station_data[
                station[ENTITY_MAC_ADDRESS]
            ] = await self.api.get_device_details(station[ENTITY_MAC_ADDRESS])
        return station_data
