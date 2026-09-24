"""Class to manage VeSync data updates."""

import asyncio
from datetime import timedelta
import logging
import time
from typing import override

from pyvesync import VeSync
from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.utils.errors import VeSyncError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import UPDATE_INTERVAL, UPDATE_INTERVAL_ENERGY

_LOGGER = logging.getLogger(__name__)

# The VeSync cloud can return a device's old state for up to two minutes after a
# command, so don't poll it in that window. It will undo the change.
COMMAND_GRACE_PERIOD = 120

type VesyncConfigEntry = ConfigEntry[VeSyncDataCoordinator]


def _device_key(device: VeSyncBaseDevice) -> str:
    """Return a key identifying a device, including its sub device number."""
    if isinstance(device.sub_device_no, int):
        return f"{device.cid}{device.sub_device_no!s}"
    return device.cid


class VeSyncDataCoordinator(DataUpdateCoordinator[None]):
    """Class representing data coordinator for VeSync devices."""

    config_entry: VesyncConfigEntry
    update_time: float | None = None

    def __init__(
        self, hass: HomeAssistant, config_entry: VesyncConfigEntry, manager: VeSync
    ) -> None:
        """Initialize."""
        self.manager = manager
        self._held_until: dict[str, float] = {}

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

        return time.time() - self.update_time >= UPDATE_INTERVAL_ENERGY

    @callback
    def async_mark_command(self, device: VeSyncBaseDevice) -> None:
        """Hold a device out of polling after a command and refresh its entities."""
        self._held_until[_device_key(device)] = time.monotonic() + COMMAND_GRACE_PERIOD
        self.async_update_listeners()

    def _is_held(self, device: VeSyncBaseDevice) -> bool:
        """Return True if the device was changed from HA too recently to poll."""
        key = _device_key(device)
        until = self._held_until.get(key)
        if until is None:
            return False
        if until <= time.monotonic():
            del self._held_until[key]
            return False
        return True

    @override
    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            devices = [
                device for device in self.manager.devices if not self._is_held(device)
            ]
            results = await asyncio.gather(
                *(device.update() for device in devices), return_exceptions=True
            )
            for device, result in zip(devices, results, strict=True):
                if isinstance(result, VeSyncError):
                    _LOGGER.error(
                        "Error updating device %s: %s", device.device_name, result
                    )
                elif isinstance(result, BaseException):
                    raise result
            errors = [r for r in results if isinstance(r, VeSyncError)]
            if devices and len(errors) == len(devices):
                raise errors[0]

            if self.should_update_energy():
                self.update_time = time.time()
                for outlet in self.manager.devices.outlets:
                    await outlet.update_energy()
        except VeSyncError as err:
            raise UpdateFailed(f"The service is unavailable: {err}") from err
