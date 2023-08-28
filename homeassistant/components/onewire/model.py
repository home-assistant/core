"""Type definitions for 1-Wire integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo


@dataclass
class OWDeviceDescription:
    """1-Wire device description class."""

    device_info: DeviceInfo

    family: str
    id: str
    path: str
    type: str
