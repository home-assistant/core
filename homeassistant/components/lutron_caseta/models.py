"""The lutron_caseta integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pylutron_caseta.smartbridge import Smartbridge

from homeassistant.helpers.entity import DeviceInfo


@dataclass
class LutronCasetaData:
    """Data for the lutron_caseta integration."""

    bridge: Smartbridge
    bridge_device: dict[str, Any]
    button_devices: dict[str, dict]
    device_info_by_device_id: dict[int, DeviceInfo]
