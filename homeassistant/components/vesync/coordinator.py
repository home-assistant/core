"""Class to manage VeSync data updates."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from pyvesync import VeSync

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import UPDATE_INTERVAL, UPDATE_INTERVAL_ENERGY

_LOGGER = logging.getLogger(__name__)

type VesyncConfigEntry = ConfigEntry[VeSyncDataCoordinator]


class VeSyncDataCoordinator(DataUpdateCoordinator[None]):
    """Class representing data coordinator for VeSync devices."""

    config_entry: VesyncConfigEntry
    update_time: datetime | None = None

    def __init__(
        self, hass: HomeAssistant, config_entry: VesyncConfigEntry, manager: VeSync
    ) -> None:
        """Initialize."""
        self.manager = manager

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="VeSyncDataCoordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def should_update_energy(self) -> bool:
        """Test if specified update interval has been exceeded."""
        if self.update_time is None:
            return True

        return datetime.now() - self.update_time >= timedelta(
            seconds=UPDATE_INTERVAL_ENERGY
        )

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""

        await self.manager.update_all_devices()

        if self.should_update_energy():
            self.update_time = datetime.now()
            for outlet in self.manager.devices.outlets:
                await outlet.update_energy()
