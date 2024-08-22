"""Utilities for Flume."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import KEY_DEVICE_LOCATION, KEY_DEVICE_LOCATION_NAME

if TYPE_CHECKING:
    from pyflume import FlumeDeviceList


def get_valid_flume_devices(flume_devices: FlumeDeviceList) -> list[dict[str, Any]]:
    """Return a list of Flume devices that have a valid location."""
    return [
        device
        for device in flume_devices.device_list
        if KEY_DEVICE_LOCATION in device
        and KEY_DEVICE_LOCATION_NAME in device[KEY_DEVICE_LOCATION]
    ]
