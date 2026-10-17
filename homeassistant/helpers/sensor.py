"""Common functions related to sensor device management."""

from functools import lru_cache
from typing import TYPE_CHECKING, Any, override

from .device_registry import DeviceInfo

if TYPE_CHECKING:
    # `sensor_state_data` is a second-party library (i.e. maintained by Home Assistant
    # core members) which is not strictly required by Home Assistant.
    # Therefore, we import it as a type hint only.
    from sensor_state_data import SensorDeviceInfo


_READ_ONLY = (
    "The device info returned by sensor_device_info_to_hass_device_info is shared"
    " and cannot be modified; copy it first with DeviceInfo(**device_info)"
)


class _SharedDeviceInfo(DeviceInfo):
    """A cached device info, which is shared and so cannot be modified."""

    __slots__ = ()

    @override
    def __setattr__(self, name: str, value: Any) -> None:
        """Refuse to modify a shared device info."""
        raise TypeError(_READ_ONLY)

    @override
    def __delattr__(self, name: str) -> None:
        """Refuse to modify a shared device info."""
        raise TypeError(_READ_ONLY)

    def __copy__(self) -> DeviceInfo:
        """Return a copy which can be modified."""
        return DeviceInfo(**self)

    def __deepcopy__(self, memo: dict[int, Any]) -> DeviceInfo:
        """Return a copy which can be modified; the cached values are strings."""
        return DeviceInfo(**self)


def sensor_device_info_to_hass_device_info(
    sensor_device_info: SensorDeviceInfo,
) -> DeviceInfo:
    """Convert a sensor_state_data sensor device info to a HA device info.

    The same device info is returned for the same values, so it cannot be modified.
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
    # Made read-only once built; the subclass adds no slots, so the class can change
    device_info.__class__ = _SharedDeviceInfo
    return device_info
