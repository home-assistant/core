"""Class to manage VeSync data updates."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyvesync import VeSync

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class VeSyncDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class representing data coordinator for VeSync devices."""

    def __init__(self, hass: HomeAssistant, manager: VeSync) -> None:
        """Initialize."""
        self._manager = manager

        super().__init__(
            hass,
            _LOGGER,
            name="VeSyncDataCoordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""

        # Using `update_all_devices` instead of `update` to avoid fetching device list every time.
        return await self.hass.async_add_executor_job(self._manager.update_all_devices)
