"""Common functions related to sensor device management."""

from functools import lru_cache
from typing import TYPE_CHECKING

from .device_registry import DeviceInfo

if TYPE_CHECKING:
    # `sensor_state_data` is a second-party library (i.e. maintained by Home Assistant
    # core members) which is not strictly required by Home Assistant.
    # Therefore, we import it as a type hint only.
    from sensor_state_data import SensorDeviceInfo


def sensor_device_info_to_hass_device_info(
    sensor_device_info: SensorDeviceInfo,
) -> DeviceInfo:
    """Convert a sensor_state_data sensor device info to a HA device info.

    The same device info is returned for the same values, so it must not be modified.
    """
    return _device_info(
        sensor_device_info.name,
        sensor_device_info.manufacturer,
        sensor_device_info.model,
    )


# Bluetooth converts every advertisement, which almost always carries the same values:
# the cached device info is cheap to build, and compares by identity
@lru_cache(maxsize=512)
def _device_info(
    name: str | None, manufacturer: str | None, model: str | None
) -> DeviceInfo:
    """Return the device info for these values, leaving None values unset."""
    device_info = DeviceInfo()
    if name is not None:
        device_info.name = name
    if manufacturer is not None:
        device_info.manufacturer = manufacturer
    if model is not None:
        device_info.model = model
    return device_info
