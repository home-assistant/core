"""Coordinator for Actron Air Neo integration."""

from datetime import datetime, timedelta
from typing import Any

from actron_neo_api import (
    ActronAirNeoACSystem,
    ActronAirNeoStatus,
    ActronNeoAPI,
    ActronNeoAPIError,
    ActronNeoAuthError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import _LOGGER, STALE_DEVICE_TIMEOUT

type ActronConfigEntry = ConfigEntry[ActronNeoDataUpdateCoordinator]

AUTH_ERROR_THRESHOLD = 3
SCAN_INTERVAL = timedelta(seconds=30)
PARALLEL_UPDATES = 0


class ActronNeoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Custom coordinator for Actron Air Neo integration."""

    def __init__(
        self, hass: HomeAssistant, entry: ActronConfigEntry, pairing_token: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Actron Neo Status",
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self.api = ActronNeoAPI(pairing_token=pairing_token)
        self.last_update_success = False
        self.last_seen: dict[str, datetime] = {}
        self.auth_error_count = 0
        self.systems: list[ActronAirNeoACSystem] = []
        self.status_objects: dict[str, ActronAirNeoStatus] = {}

    async def _async_setup(self) -> None:
        """Perform initial setup, including refreshing the token."""
        try:
            await self.api.refresh_token()
            self.systems = await self.api.get_ac_systems()
            self.auth_error_count = 0
        except ActronNeoAuthError:
            _LOGGER.error(
                "Authentication error while setting up Actron Neo integration"
            )
            raise
        except ActronNeoAPIError as err:
            _LOGGER.error("API error while setting up Actron Neo integration: %s", err)
            raise

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch updates and merge incremental changes into the full state."""
        try:
            await self.api.update_status()
            self.last_update_success = True
            self.auth_error_count = 0
            current_time = dt_util.utcnow()

            for system in self.systems:
                serial = system.get("serial")
                self.last_seen[serial] = current_time
                status = self.api.state_manager.get_status(serial)
                self.status_objects[serial] = status
        except ActronNeoAuthError as err:
            self.last_update_success = False
            self.auth_error_count += 1
            _LOGGER.warning(
                "Authentication error while updating Actron Neo data. "
                "Device may be unavailable"
            )
            raise UpdateFailed("Authentication error") from err
        except ActronNeoAPIError as err:
            self.last_update_success = False
            _LOGGER.warning(
                "Error communicating with Actron Neo API: %s. "
                "Device may be unavailable",
                err,
            )
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return self.status_objects[serial]

    def is_device_stale(self, system_id: str) -> bool:
        """Check if a device is stale (not seen for a while)."""
        if system_id not in self.last_seen:
            return True

        last_seen_time = self.last_seen[system_id]
        current_time = dt_util.utcnow()
        return (current_time - last_seen_time) > STALE_DEVICE_TIMEOUT

    def get_status(self, serial_number: str) -> ActronAirNeoStatus:
        """Get the stored status object for a system."""
        if serial_number in self.status_objects:
            return self.status_objects[serial_number]
        return self.api.state_manager.get_status(serial_number)
