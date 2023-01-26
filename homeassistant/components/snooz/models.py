"""Data models for the Snooz component."""

from dataclasses import dataclass

from bleak.backends.device import BLEDevice
from pysnooz.device import SnoozDevice


@dataclass
class SnoozConfigurationData:
    """Configuration data for Snooz."""

    ble_device: BLEDevice
    device: SnoozDevice
    title: str
