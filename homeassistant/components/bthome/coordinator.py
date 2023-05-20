"""The BTHome Bluetooth integration."""
from collections.abc import Callable
from logging import Logger
from typing import Any

from bthome_ble import BTHomeBluetoothDeviceData

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant


class BTHomePassiveBluetoothProcessorCoordinator(PassiveBluetoothProcessorCoordinator):
    """Define a BTHome Bluetooth Passive Update Processor Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        address: str,
        mode: BluetoothScanningMode,
        update_method: Callable[[BluetoothServiceInfoBleak], Any],
        device_data: BTHomeBluetoothDeviceData,
        discovered_device_classes: set[str],
        connectable: bool = False,
    ) -> None:
        """Initialize the BTHome Bluetooth Passive Update Processor Coordinator."""
        super().__init__(hass, logger, address, mode, update_method, connectable)
        self.discovered_device_classes = discovered_device_classes
        self.device_data = device_data


class BTHomePassiveBluetoothDataProcessor(PassiveBluetoothDataProcessor):
    """Define a BTHome Bluetooth Passive Update Data Processor."""

    coordinator: BTHomePassiveBluetoothProcessorCoordinator
