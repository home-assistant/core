"""Data models for the Snooz component."""

from dataclasses import dataclass

from bleak.backends.device import BLEDevice
from pysnooz import SnoozAdvertisementData, SnoozDevice


@dataclass
class SnoozConfigurationData:
    """Configuration data for Snooz."""

    ble_device: BLEDevice
    adv_data: SnoozAdvertisementData
    device: SnoozDevice
    title: str
