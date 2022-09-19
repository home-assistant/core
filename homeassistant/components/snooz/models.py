"""Data models for the Snooz component."""

from bleak.backends.device import BLEDevice
from pysnooz.device import SnoozDevice

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)


class SnoozConfigurationData:
    """Configuration data for Snooz."""

    def __init__(
        self,
        ble_device: BLEDevice,
        device: SnoozDevice,
        coordinator: PassiveBluetoothProcessorCoordinator,
    ) -> None:
        """Initialize configuration data."""
        self.ble_device = ble_device
        self.device = device
        self.coordinator = coordinator
