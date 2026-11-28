"""The BTHome Bluetooth integration."""

from collections.abc import Callable
from logging import Logger
from typing import override

from bthome_ble import BTHomeBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_event_driven,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

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
        last_processed: dict[str, tuple[dict[str, bytes], float]],
        connectable: bool = False,
    ) -> None:
        """Initialize the BTHome Bluetooth Passive Update Processor Coordinator."""
        super().__init__(hass, logger, address, mode, update_method, connectable)
        self.discovered_event_classes = discovered_event_classes
        # Service data and time last processed per address, kept across reloads
        self.last_processed = last_processed
        self.device_data = device_data
        self.entry = entry
        # Track whether we've already logged the encryption downgrade this session.
        self.encryption_downgrade_logged = False
        self._cancel_event_driven: CALLBACK_TYPE | None = None
        self.replaying = False
        self.paused = False

    @property
    def sleepy_device(self) -> bool:
        """Return True if the device is a sleepy device."""
        return self.entry.data.get(CONF_SLEEPY_DEVICE, self.device_data.sleepy_device)  # type: ignore[no-any-return]

    @callback
    @override
    def async_start(self) -> CALLBACK_TYPE:
        """Start the coordinator, flagging the history it replays."""
        self.replaying = True
        try:
            return super().async_start()
        finally:
            self.replaying = False

    @callback
    def async_set_event_driven(self, event_driven: bool) -> None:
        """Take new packets of a sleepy device from any Bluetooth scanner."""
        if event_driven and self._cancel_event_driven is None:
            self._cancel_event_driven = async_register_event_driven(
                self.hass, self.address
            )
        elif not event_driven and self._cancel_event_driven is not None:
            self._cancel_event_driven()
            self._cancel_event_driven = None


class BTHomePassiveBluetoothDataProcessor[_T](
    PassiveBluetoothDataProcessor[_T, SensorUpdate]
):
    """Define a BTHome Bluetooth Passive Update Data Processor."""

    coordinator: BTHomePassiveBluetoothProcessorCoordinator
