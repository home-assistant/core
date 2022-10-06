"""Data models for the Snooz component."""

from bleak.backends.device import BLEDevice
from pysnooz.device import SnoozDevice


class SnoozConfigurationData:
    """Configuration data for Snooz."""

    def __init__(self, ble_device: BLEDevice, device: SnoozDevice) -> None:
        """Initialize configuration data."""
        self.ble_device = ble_device
        self.device = device
