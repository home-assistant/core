"""Models for Lyngdorf integration."""

from dataclasses import dataclass

from lyngdorf import LyngdorfReceiver

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo


@dataclass
class LyngdorfRuntimeData:
    """Runtime data for Lyngdorf integration."""

    receiver: LyngdorfReceiver
    device_info: DeviceInfo
    zone_b_device_info: DeviceInfo | None


type LyngdorfConfigEntry = ConfigEntry[LyngdorfRuntimeData]
