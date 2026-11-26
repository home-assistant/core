"""The BTHome Bluetooth integration."""

from collections.abc import Callable
from logging import Logger

from bthome_ble import BTHomeBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothCallbackReplay,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_last_service_info,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant, callback

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
        super().__init__(
            hass,
            logger,
            address,
            mode,
            update_method,
            connectable,
            # The last packet in the Bluetooth history can be older than one
            # taken from a non-owner scanner; entities restore the latest state.
            replay=(
                BluetoothCallbackReplay.DISABLED
                if entry.data.get(CONF_SLEEPY_DEVICE)
                else BluetoothCallbackReplay.OLDEST_FIRST
            ),
        )
        self.discovered_event_classes = discovered_event_classes
        self.device_data = device_data
        self.entry = entry
        # Track whether we've already logged the encryption downgrade this session.
        self.encryption_downgrade_logged = False

    @property
    def sleepy_device(self) -> bool:
        """Return True if the device is a sleepy device."""
        return self.entry.data.get(CONF_SLEEPY_DEVICE, self.device_data.sleepy_device)  # type: ignore[no-any-return]

    @callback
    def async_handle_advertisement(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Process a new packet of a sleepy device heard by a non-owner scanner.

        The Bluetooth manager keeps a device on its current scanner for up to
        15 minutes when no advertising interval is known, which drops the
        packets of trigger-based devices that only another scanner hears.
        The packet id filter of the parser drops the copies of one packet.
        """
        if not self.sleepy_device or self.device_data.packet_id is None:
            return
        if (
            last_service_info := async_last_service_info(
                self.hass, self.address, self.connectable
            )
        ) is None or last_service_info.source == service_info.source:
            return
        if (
            previous := self.device_data.last_service_info
        ) is not None and previous.service_data == service_info.service_data:
            return
        self._async_handle_bluetooth_event(service_info, BluetoothChange.ADVERTISEMENT)


class BTHomePassiveBluetoothDataProcessor[_T](
    PassiveBluetoothDataProcessor[_T, SensorUpdate]
):
    """Define a BTHome Bluetooth Passive Update Data Processor."""

    coordinator: BTHomePassiveBluetoothProcessorCoordinator
