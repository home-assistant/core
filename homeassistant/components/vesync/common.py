"""Common utilities for VeSync Component."""

import logging

from pyvesync import VeSync
from pyvesync.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.vesyncoutlet import VeSyncOutlet
from pyvesync.vesyncswitch import VeSyncWallSwitch

from homeassistant.core import HomeAssistant

from .const import VeSyncFanDevice, VeSyncHumidifierDevice

_LOGGER = logging.getLogger(__name__)


def rgetattr(obj: object, attr: str):
    """Return a string in the form word.1.2.3 and return the item as 3. Note that this last value could be in a dict as well."""
    _this_func = rgetattr
    sp = attr.split(".", 1)
    if len(sp) == 1:
        left, right = sp[0], ""
    else:
        left, right = sp

    if isinstance(obj, dict):
        obj = obj.get(left)
    elif hasattr(obj, left):
        obj = getattr(obj, left)
    else:
        return None

    if right:
        obj = _this_func(obj, right)

    return obj


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


def is_fan(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a fan."""

    return isinstance(device, VeSyncFanDevice)


def is_outlet(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents an outlet."""

    return isinstance(device, VeSyncOutlet)


def is_wall_switch(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a wall switch, note this doessn't include dimming switches."""

    return isinstance(device, VeSyncWallSwitch)
