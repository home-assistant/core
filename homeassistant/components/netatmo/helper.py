"""Helper for Netatmo integration."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from pyatmo.modules.device_types import DeviceType as NetatmoDeviceType


# The stringified DeviceType members historically in pyatmo were rendered as 'DeviceType.<name>'.
# This rendering has been changed (StrEnum), this below helper does that manually to avoid breaking
# unique IDs for existing installations
def device_type_to_str(device_type: NetatmoDeviceType) -> str:
    """Convert a device type to a string."""
# The stringified DeviceType members historically in pyatmo were rendered as 'DeviceType.<name>'.
# This rendering has been changed (StrEnum), this below helper does that manually to avoid breaking
# unique IDs for existing installations
def device_type_to_str(device_type: NetatmoDeviceType) -> str:
    """Convert a device type to a string.

    Used to generate backwards compatible unique ids.
    """
    return f"{type(device_type).__name__}.{device_type}"


@dataclass
class NetatmoArea:
    """Class for keeping track of an area."""

    area_name: str
    lat_ne: float
    lon_ne: float
    lat_sw: float
    lon_sw: float
    mode: str
    show_on_map: bool
    uuid: UUID = uuid4()
