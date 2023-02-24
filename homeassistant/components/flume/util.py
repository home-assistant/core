"""Utilities for Flume."""

from __future__ import annotations

from typing import Any

from pyflume import FlumeDeviceList

from .const import KEY_DEVICE_LOCATION, KEY_DEVICE_LOCATION_NAME


def get_valid_flume_devices(flume_devices: FlumeDeviceList) -> list[dict[str, Any]]:
    """Return a list of Flume devices that have a valid location."""
    return [
        device
        for device in flume_devices.device_list
        if KEY_DEVICE_LOCATION in device
        and KEY_DEVICE_LOCATION_NAME in device[KEY_DEVICE_LOCATION]
    ]
