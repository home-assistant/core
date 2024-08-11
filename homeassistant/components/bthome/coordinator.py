"""The BTHome Bluetooth integration."""

from collections.abc import Callable
from logging import Logger

from bthome_ble import BTHomeBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant

from .const import CONF_SLEEPY_DEVICE
from .types import BTHomeConfigEntry


class BTHomePassiveBluetoothProcessorCoordinator(
    PassiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Define a BTHome Bluetooth Passive Update Processor Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        address: str,
        mode: BluetoothScanningMode,
        update_method: Callable[[BluetoothServiceInfoBleak], SensorUpdate],
        device_data: BTHomeBluetoothDeviceData,
        discovered_event_classes: set[str],
        entry: BTHomeConfigEntry,
        connectable: bool = False,
    ) -> None:
        """Initialize the BTHome Bluetooth Passive Update Processor Coordinator."""
        super().__init__(hass, logger, address, mode, update_method, connectable)
        self.discovered_event_classes = discovered_event_classes
        self.device_data = device_data
        self.entry = entry

    @property
    def sleepy_device(self) -> bool:
        """Return True if the device is a sleepy device."""
        return self.entry.data.get(CONF_SLEEPY_DEVICE, self.device_data.sleepy_device)


class BTHomePassiveBluetoothDataProcessor[_T](
    PassiveBluetoothDataProcessor[_T, SensorUpdate]
):
    """Define a BTHome Bluetooth Passive Update Data Processor."""

    coordinator: BTHomePassiveBluetoothProcessorCoordinator
