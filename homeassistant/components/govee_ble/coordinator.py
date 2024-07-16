"""The govee Bluetooth integration."""

from collections.abc import Callable
from logging import Logger

from govee_ble import GoveeBluetoothDeviceData, SensorUpdate

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

type GoveeBLEConfigEntry = ConfigEntry[GoveeBLEBluetoothProcessorCoordinator]


def process_service_info(
    hass: HomeAssistant,
    entry: GoveeBLEConfigEntry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    coordinator = entry.runtime_data
    update = coordinator.device_data.update(service_info)
    if update.events:
        address = service_info.device.address
        for event in update.events.values():
            event_type = event.event_type
            async_dispatcher_send(
                hass,
                format_event_dispatcher_name(address, event_type),
            )

    return update


def format_event_dispatcher_name(address: str, event_type: str) -> str:
    """Format an event dispatcher name."""
    return f"{DOMAIN}_{address}_{event_type}"


class GoveeBLEBluetoothProcessorCoordinator(
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
        device_data: GoveeBluetoothDeviceData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Govee BLE Bluetooth Passive Update Processor Coordinator."""
        super().__init__(hass, logger, address, mode, update_method)
        self.device_data = device_data
        self.entry = entry
