"""DataUpdateCoordinator for the Ambient Weather Network integration."""

from __future__ import annotations

from typing import Any, cast

from aioambient import OpenAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ENTITY_MAC_ADDRESS, LOGGER, SCAN_INTERVAL


class AmbientNetworkDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """The Ambient Network Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, api: OpenAPI) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest data from the Ambient Network."""

        response = await self.api.get_device_details(
            self.config_entry.data[ENTITY_MAC_ADDRESS]
        )

        if response is None or (last_data := response.get("lastData")) is None:
            # Return previous data
            return self.data  # pragma: no cover

        return cast(dict[str, Any], last_data)
