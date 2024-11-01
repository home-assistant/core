"""The Xiaomi BLE integration."""

from collections.abc import Callable, Coroutine
from logging import Logger
from typing import Any

from xiaomi_ble import SensorUpdate, XiaomiBluetoothDeviceData

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer

from .const import CONF_SLEEPY_DEVICE
from .types import XiaomiBLEConfigEntry


class XiaomiActiveBluetoothProcessorCoordinator(
    ActiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Define a Xiaomi Bluetooth Active Update Processor Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        *,
        address: str,
        mode: BluetoothScanningMode,
        update_method: Callable[[BluetoothServiceInfoBleak], SensorUpdate],
        needs_poll_method: Callable[[BluetoothServiceInfoBleak, float | None], bool],
        device_data: XiaomiBluetoothDeviceData,
        discovered_event_classes: set[str],
        poll_method: Callable[
            [BluetoothServiceInfoBleak],
            Coroutine[Any, Any, SensorUpdate],
        ]
        | None = None,
        poll_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None,
        entry: XiaomiBLEConfigEntry,
        connectable: bool = True,
    ) -> None:
        """Initialize the Xiaomi Bluetooth Active Update Processor Coordinator."""
        super().__init__(
            hass=hass,
            logger=logger,
            address=address,
            mode=mode,
            update_method=update_method,
            needs_poll_method=needs_poll_method,
            poll_method=poll_method,
            poll_debouncer=poll_debouncer,
            connectable=connectable,
        )
        self.discovered_event_classes = discovered_event_classes
        self.device_data = device_data
        self.entry = entry

    @property
    def sleepy_device(self) -> bool:
        """Return True if the device is a sleepy device."""
        return self.entry.data.get(CONF_SLEEPY_DEVICE, self.device_data.sleepy_device)


class XiaomiPassiveBluetoothDataProcessor[_T](
    PassiveBluetoothDataProcessor[_T, SensorUpdate]
):
    """Define a Xiaomi Bluetooth Passive Update Data Processor."""

    coordinator: XiaomiActiveBluetoothProcessorCoordinator
