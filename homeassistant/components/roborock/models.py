"""Roborock Models."""
from dataclasses import dataclass, field

from roborock.containers import HomeDataDevice, HomeDataProduct, NetworkInfo
from roborock.typing import RoborockDeviceProp


@dataclass
class RoborockHassDeviceInfo:
    """A model to describe roborock devices."""

    device: HomeDataDevice
    network_info: NetworkInfo
    product: HomeDataProduct
    props: RoborockDeviceProp = field(default_factory=RoborockDeviceProp())
