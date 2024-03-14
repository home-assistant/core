"""Roborock Models."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from roborock.containers import HomeDataDevice, HomeDataProduct, NetworkInfo
from roborock.roborock_typing import DeviceProp

from homeassistant.helpers.restore_state import ExtraStoredData


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
