"""Roborock Models."""
from dataclasses import dataclass

from roborock import HomeDataProduct, RoborockDeviceProp, RoborockLocalDeviceInfo


@dataclass
class RoborockHassDeviceInfo(RoborockLocalDeviceInfo):
    """A model to describe roborock devices."""

    product: HomeDataProduct
    props: RoborockDeviceProp | None = None
