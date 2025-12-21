"""Roborock Models."""

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from roborock.data import (
    CleanSummaryWithDetail,
    Consumable,
    DnDTimer,
    HomeDataDevice,
    HomeDataProduct,
    NetworkInfo,
    Status,
)
from vacuum_map_parser_base.map_data import MapData

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceState:
    """Data about the current state of a device."""

    status: Status
    dnd_timer: DnDTimer
    consumable: Consumable
    clean_summary: CleanSummaryWithDetail


@dataclass
class RoborockHassDeviceInfo:
    """A model to describe roborock devices."""

    device: HomeDataDevice
    network_info: NetworkInfo
    product: HomeDataProduct

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Turn RoborockHassDeviceInfo into a dictionary."""
        return {
            "device": self.device.as_dict(),
            "network_info": self.network_info.as_dict(),
            "product": self.product.as_dict(),
        }


@dataclass
class RoborockA01HassDeviceInfo:
    """A model to describe A01 roborock devices."""

    device: HomeDataDevice
    product: HomeDataProduct

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Turn RoborockA01HassDeviceInfo into a dictionary."""
        return {
            "device": self.device.as_dict(),
            "product": self.product.as_dict(),
        }


@dataclass
class RoborockMapInfo:
    """A model to describe all information about a map we may want."""

    flag: int
    name: str
    image: bytes | None
    last_updated: datetime
    map_data: MapData | None
