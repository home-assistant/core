"""Roborock Models."""

from dataclasses import dataclass
from typing import Any

from roborock.containers import HomeDataDevice, HomeDataProduct, NetworkInfo
from roborock.roborock_typing import DeviceProp


@dataclass
class RoborockHassDeviceInfo:
    """A model to describe roborock devices."""

    device: HomeDataDevice
    network_info: NetworkInfo
    product: HomeDataProduct
    props: DeviceProp

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Turn RoborockHassDeviceInfo into a dictionary."""
        return {
            "device": self.device.as_dict(),
            "network_info": self.network_info.as_dict(),
            "product": self.product.as_dict(),
            "props": self.props.as_dict(),
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
    rooms: dict[int, str]
