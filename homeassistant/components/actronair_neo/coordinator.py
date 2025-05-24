"""Coordinator for Actron Air Neo integration."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from actron_neo_api import (
    ActronAirNeoACSystem,
    ActronAirNeoStatus,
    ActronNeoAPI,
    ActronNeoAPIError,
    ActronNeoAuthError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import _LOGGER, STALE_DEVICE_TIMEOUT


@dataclass
class ActronNeoRuntimeData:
    """Runtime data for the Actron Air Neo integration."""

    api_coordinator: "ActronNeoApiCoordinator"
    system_coordinators: dict[str, "ActronNeoSystemCoordinator"]


type ActronNeoConfigEntry = ConfigEntry[ActronNeoRuntimeData]

AUTH_ERROR_THRESHOLD = 3
SCAN_INTERVAL = timedelta(seconds=30)
PARALLEL_UPDATES = 0


class ActronNeoApiCoordinator:
    """Coordinator for Actron Neo API."""

    def __init__(self, hass: HomeAssistant, entry: ActronNeoConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.api = ActronNeoAPI(pairing_token=entry.data[CONF_API_TOKEN])
        self.systems: list[ActronAirNeoACSystem] = []

    async def async_setup(self) -> bool:
        """Perform initial setup, including refreshing the token."""
        try:
            await self.api.refresh_token()
            systems = await self.api.get_ac_systems()
            self.systems = systems
        except ActronNeoAuthError:
            _LOGGER.error(
                "Authentication error while setting up Actron Neo integration"
            )
            raise
        except ActronNeoAPIError as err:
            _LOGGER.error("API error while setting up Actron Neo integration: %s", err)
            raise
        return True


class ActronNeoSystemCoordinator(DataUpdateCoordinator[ActronAirNeoACSystem]):
    """System coordinator for Actron Air Neo integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ActronNeoConfigEntry,
        api_coordinator: ActronNeoApiCoordinator,
        system: ActronAirNeoACSystem,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Neo Status",
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.system = system
        self.serial_number = system["serial"]
        self.api = api_coordinator.api
        self.status: ActronAirNeoStatus = self.api.state_manager.get_status(
            self.serial_number
        )
        self.last_seen = dt_util.utcnow()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch updates and merge incremental changes into the full state."""
        self.last_seen = dt_util.utcnow()
        self.status = self.api.state_manager.get_status(self.serial_number)
        return self.status

    def is_device_stale(self) -> bool:
        """Check if a device is stale (not seen for a while)."""
        return (dt_util.utcnow() - self.last_seen) > STALE_DEVICE_TIMEOUT
