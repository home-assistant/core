"""Coordinator for Actron Air integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from actron_neo_api import ActronAirNeoACSystem, ActronAirNeoStatus, ActronNeoAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import _LOGGER

STALE_DEVICE_TIMEOUT = timedelta(hours=24)
ERROR_NO_SYSTEMS_FOUND = "no_systems_found"
ERROR_UNKNOWN = "unknown_error"


@dataclass
class ActronAirRuntimeData:
    """Runtime data for the Actron Air integration."""

    api: ActronNeoAPI
    system_coordinators: dict[str, ActronAirSystemCoordinator]


type ActronAirConfigEntry = ConfigEntry[ActronAirRuntimeData]

AUTH_ERROR_THRESHOLD = 3
SCAN_INTERVAL = timedelta(seconds=30)


class ActronAirSystemCoordinator(DataUpdateCoordinator[ActronAirNeoACSystem]):
    """System coordinator for Actron Air integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ActronAirConfigEntry,
        api: ActronNeoAPI,
        system: ActronAirNeoACSystem,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Air Status",
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.system = system
        self.serial_number = system["serial"]
        self.api = api
        self.status = self.api.state_manager.get_status(
            self.serial_number
        )
        self.last_seen = dt_util.utcnow()

    async def _async_update_data(self) -> ActronAirNeoStatus:
        """Fetch updates and merge incremental changes into the full state."""
        await self.api.update_status()
        self.status = self.api.state_manager.get_status(self.serial_number)
        self.last_seen = dt_util.utcnow()
        return self.status

    def is_device_stale(self) -> bool:
        """Check if a device is stale (not seen for a while)."""
        return (dt_util.utcnow() - self.last_seen) > STALE_DEVICE_TIMEOUT
