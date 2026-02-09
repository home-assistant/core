"""Class to manage VeSync data updates."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from pyvesync import VeSync
from pyvesync.utils.errors import VeSyncError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
        self._last_device_states: dict[str, dict] = {}

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="VeSyncDataCoordinator",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def _get_device_state_hash(self, device) -> str:
        """Generate a hash of the device state for change detection."""
        state = {
            "status": getattr(device, "status", None),
            "enabled": getattr(device, "enabled", None),
        }
        return str(state)

    def _has_state_changed(self, device) -> bool:
        """Check if device state has changed since last update."""
        device_id = getattr(device, "cid", None)
        if device_id is None:
            return True

        current_hash = self._get_device_state_hash(device)
        last_hash = self._last_device_states.get(device_id)

        if last_hash != current_hash:
            self._last_device_states[device_id] = current_hash
            return True
        return False

    def should_update_energy(self) -> bool:
        """Test if specified update interval has been exceeded."""
        if self.update_time is None:
            return True

        return datetime.now() - self.update_time >= timedelta(
            seconds=UPDATE_INTERVAL_ENERGY
        )

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            await self.manager.update_all_devices()

            # Log state changes for debugging
            changed_devices = 0
            for device in self.manager.devices.all_devices:
                if self._has_state_changed(device):
                    changed_devices += 1

            if changed_devices > 0:
                _LOGGER.debug("State changed for %d devices", changed_devices)
            else:
                _LOGGER.debug("No device state changes detected")

            if self.should_update_energy():
                self.update_time = datetime.now()
                for outlet in self.manager.devices.outlets:
                    await outlet.update_energy()
        except VeSyncError as err:
            _LOGGER.warning("VeSync API error: %s", err)
            raise UpdateFailed(f"The service is unavailable: {err}") from err
