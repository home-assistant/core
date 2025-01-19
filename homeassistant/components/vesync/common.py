"""Common utilities for VeSync Component."""

import logging

from pyvesync import VeSync
from pyvesync.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.vesyncoutlet import VeSyncOutlet
from pyvesync.vesyncswitch import VeSyncWallSwitch

from homeassistant.core import HomeAssistant

from .const import VeSyncHumidifierDevice

_LOGGER = logging.getLogger(__name__)


async def async_generate_device_list(
    hass: HomeAssistant, manager: VeSync
) -> list[VeSyncBaseDevice]:
    """Assign devices to proper component."""
    devices: list[VeSyncBaseDevice] = []

    await hass.async_add_executor_job(manager.update)

    devices.extend(manager.fans)
    devices.extend(manager.bulbs)
    devices.extend(manager.outlets)
    devices.extend(manager.switches)

    return devices


def is_humidifier(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a humidifier."""

    return isinstance(device, VeSyncHumidifierDevice)


def is_outlet(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents an outlet."""

    return isinstance(device, VeSyncOutlet)


def is_wall_switch(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a wall switch, note this doessn't include dimming switches."""

    return isinstance(device, VeSyncWallSwitch)
