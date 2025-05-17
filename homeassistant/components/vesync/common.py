"""Common utilities for VeSync Component."""

import logging

from pyvesync.base_devices import VeSyncHumidifier
from pyvesync.base_devices.fan_base import VeSyncFanBase
from pyvesync.base_devices.outlet_base import VeSyncOutlet
from pyvesync.base_devices.purifier_base import VeSyncPurifier
from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.devices.vesyncswitch import VeSyncWallSwitch

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


def is_humidifier(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a humidifier."""

    return isinstance(device, VeSyncHumidifier)


def is_outlet(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents an outlet."""

    return isinstance(device, VeSyncOutlet)


def is_wall_switch(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a wall switch, note this doessn't include dimming switches."""

    return isinstance(device, VeSyncWallSwitch)


def is_fan(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a fan."""

    return isinstance(device, VeSyncFanBase)


def is_purifier(device: VeSyncBaseDevice) -> bool:
    """Check if the device represents a fan."""

    return isinstance(device, VeSyncPurifier)
