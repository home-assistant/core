"""Common functions related to sensor device management."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant import const

from .device_registry import DeviceInfo

if TYPE_CHECKING:
    # `sensor_state_data` is a second-party library (i.e. maintained by Home Assistant
    # core members) which is not strictly required by Home Assistant.
    # Therefore, we import it as a type hint only.
    from sensor_state_data import SensorDeviceInfo


def sensor_device_info_to_hass_device_info(
    sensor_device_info: SensorDeviceInfo,
) -> DeviceInfo:
    """Convert a sensor_state_data sensor device info to a HA device info."""
    device_info = DeviceInfo()
    if sensor_device_info.name is not None:
        device_info[const.ATTR_NAME] = sensor_device_info.name
    if sensor_device_info.manufacturer is not None:
        device_info[const.ATTR_MANUFACTURER] = sensor_device_info.manufacturer
    if sensor_device_info.model is not None:
        device_info[const.ATTR_MODEL] = sensor_device_info.model
    return device_info
