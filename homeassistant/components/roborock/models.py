"""Roborock Models."""
from dataclasses import dataclass

from roborock.containers import HomeDataDevice, HomeDataProduct, NetworkInfo
from roborock.typing import RoborockDeviceProp


@dataclass
class RoborockHassDeviceInfo:
    """A model to describe roborock devices."""

    device: HomeDataDevice
    network_info: NetworkInfo
    product: HomeDataProduct
    props: RoborockDeviceProp
