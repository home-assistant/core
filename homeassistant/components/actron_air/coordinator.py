"""Coordinator for Actron Air integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from actron_neo_api import (
    ActronAirACSystem,
    ActronAirAPI,
    ActronAirAPIError,
    ActronAirAuthError,
    ActronAirStatus,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
STALE_DEVICE_TIMEOUT = timedelta(minutes=5)
ERROR_NO_SYSTEMS_FOUND = "no_systems_found"
ERROR_UNKNOWN = "unknown_error"


@dataclass
class ActronAirRuntimeData:
    """Runtime data for the Actron Air integration."""

    api: ActronAirAPI
    system_coordinators: dict[str, ActronAirSystemCoordinator]


type ActronAirConfigEntry = ConfigEntry[ActronAirRuntimeData]


class ActronAirSystemCoordinator(DataUpdateCoordinator[ActronAirACSystem]):
    """System coordinator for Actron Air integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ActronAirConfigEntry,
        api: ActronAirAPI,
        system: ActronAirACSystem,
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
        self.status = self.api.state_manager.get_status(self.serial_number)
        self.last_seen = dt_util.utcnow()

    async def _async_update_data(self) -> ActronAirStatus:
        """Fetch updates and merge incremental changes into the full state."""
        try:
            await self.api.update_status()
        except ActronAirAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from err
        except ActronAirAPIError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": repr(err)},
            ) from err

        self.status = self.api.state_manager.get_status(self.serial_number)
        self.last_seen = dt_util.utcnow()
        return self.status

    def is_device_stale(self) -> bool:
        """Check if a device is stale (not seen for a while)."""
        return (dt_util.utcnow() - self.last_seen) > STALE_DEVICE_TIMEOUT
