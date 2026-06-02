"""Helper for Netatmo integration."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from pyatmo.modules.device_types import DeviceType as NetatmoDeviceType


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
    uuid: UUID = field(default_factory=uuid4)
