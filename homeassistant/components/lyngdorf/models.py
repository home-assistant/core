"""Models for Lyngdorf integration."""

from __future__ import annotations

from dataclasses import dataclass

from lyngdorf.device import Receiver

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo


@dataclass
class LyngdorfRuntimeData:
    """Runtime data for Lyngdorf integration."""

    receiver: Receiver
    device_info: DeviceInfo


type LyngdorfConfigEntry = ConfigEntry[LyngdorfRuntimeData]
