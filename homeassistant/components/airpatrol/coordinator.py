"""Data update coordinator for AirPatrol."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from airpatrol.api import AirPatrolAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


class AirPatrolDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Class to manage fetching AirPatrol data."""

    def __init__(
        self, hass: HomeAssistant, api: AirPatrolAPI, config_entry: ConfigEntry
    ) -> None:
        """Initialize."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            name=f"AirPatrol {config_entry.data['email']}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Fetch data from API."""
        try:
            return await self.api.get_data()
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with AirPatrol API: {err}"
            ) from err
