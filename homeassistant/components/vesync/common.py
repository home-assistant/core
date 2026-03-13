"""Common utilities for VeSync Component."""

import logging
from typing import TypeGuard

from pyvesync.base_devices import VeSyncHumidifier
from pyvesync.base_devices.fan_base import VeSyncFanBase
from pyvesync.base_devices.fryer_base import VeSyncFryer
from pyvesync.base_devices.outlet_base import VeSyncOutlet
from pyvesync.base_devices.purifier_base import VeSyncPurifier
from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.const import ProductTypes
from pyvesync.devices.vesyncswitch import VeSyncWallSwitch

from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)


def rgetattr(obj: object, attr: str) -> object | str | None:
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


def is_humidifier(device: VeSyncBaseDevice) -> TypeGuard[VeSyncHumidifier]:
    """Check if the device represents a humidifier."""

    return device.product_type == ProductTypes.HUMIDIFIER


def is_fan(device: VeSyncBaseDevice) -> TypeGuard[VeSyncFanBase]:
    """Check if the device represents a fan."""

    return device.product_type == ProductTypes.FAN


def is_outlet(device: VeSyncBaseDevice) -> TypeGuard[VeSyncOutlet]:
    """Check if the device represents an outlet."""

    return device.product_type == ProductTypes.OUTLET


def is_wall_switch(device: VeSyncBaseDevice) -> TypeGuard[VeSyncWallSwitch]:
    """Check if the device represents a wall switch, note this doessn't include dimming switches."""
    if device.product_type != ProductTypes.SWITCH:
        return False

    return getattr(device, "supports_dimmable", False) is False


def is_purifier(device: VeSyncBaseDevice) -> TypeGuard[VeSyncPurifier]:
    """Check if the device represents an air purifier."""

    return device.product_type == ProductTypes.PURIFIER


def is_air_fryer(device: VeSyncBaseDevice) -> TypeGuard[VeSyncFryer]:
    """Check if the device represents an air fryer."""

    return device.product_type == ProductTypes.AIR_FRYER


def supports_timer(device: VeSyncBaseDevice) -> bool:
    """Check if the device has timer state.

    Timer state can be present in the device.state.timer attribute.
    """
    try:
        _ = device.state.timer
    except AttributeError:
        return False
    return True


def get_timer_remaining_minutes(device: VeSyncBaseDevice) -> float:
    """Return timer remaining in minutes from device.state.timer.remaining (seconds)."""
    if not supports_timer(device):
        raise HomeAssistantError("Device does not support timer adjustment.")
    timer = device.state.timer
    if timer is None:
        return 0.0
    return timer.remaining / 60.0
