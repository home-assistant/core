"""DataUpdateCoordinator for the Ambient Weather Network integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from aioambient import OpenAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ENTITY_MAC_ADDRESS, ENTITY_STATIONS, LOGGER


class AmbientNetworkDataUpdateCoordinator(DataUpdateCoordinator):
    """The Ambient Network Data Update Coordinator."""

    def __init__(
        self, hass: HomeAssistant, api: OpenAPI, scan_interval: timedelta
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=scan_interval)
        self.api = api

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch the latest data from the Ambient Network."""

        station_data: dict[str, Any] = {}
        if self.config_entry is not None:
            for station in self.config_entry.data[ENTITY_STATIONS]:
                station_data[
                    station[ENTITY_MAC_ADDRESS]
                ] = await self.api.get_device_details(station[ENTITY_MAC_ADDRESS])
            return station_data

        return None  # pragma: no cover
