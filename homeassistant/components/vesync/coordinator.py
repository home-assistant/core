"""Class to manage VeSync data updates."""

from __future__ import annotations

from datetime import timedelta
import logging

from pyvesync import VeSync

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class VeSyncDataCoordinator(DataUpdateCoordinator[None]):
    """Class representing data coordinator for VeSync devices."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, manager: VeSync
    ) -> None:
        """Initialize."""
        self._manager = manager

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="VeSyncDataCoordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        return await self.hass.async_add_executor_job(self.update_data_all)

    def update_data_all(self) -> None:
        """Update all the devices."""

        # Using `update_all_devices` instead of `update` to avoid fetching device list every time.
        self._manager.update_all_devices()
        # Vesync updates energy on applicable devices every 6 hours
        self._manager.update_energy()
