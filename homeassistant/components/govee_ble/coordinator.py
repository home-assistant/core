"""The govee Bluetooth integration."""

from collections.abc import Callable
from logging import Logger

from govee_ble import GoveeBluetoothDeviceData, ModelInfo, SensorUpdate, get_model_info

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_DEVICE_TYPE, DOMAIN

type GoveeBLEConfigEntry = ConfigEntry[GoveeBLEBluetoothProcessorCoordinator]

# Models such as the H5074 carry their measurements only in the scan response,
# so the scanner must stay active long enough to capture one; the default 10s
# window misses them most cycles. 30s is the longest active window habluetooth
# allows (AUTO_WINDOW_MAX_DURATION) and reliably spans a full broadcast cycle.
ACTIVE_SCAN_DURATION = 30.0


def process_service_info(
    hass: HomeAssistant,
    entry: GoveeBLEConfigEntry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak.

    Runs side effects and returns sensor data.
    """
    coordinator = entry.runtime_data
    data = coordinator.device_data
    update = data.update(service_info)
    if not coordinator.model_info and (device_type := data.device_type):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_DEVICE_TYPE: device_type}
        )
        coordinator.set_model_info(device_type)
    if update.events and hass.state is CoreState.running:
        # Do not fire events on data restore
        address = service_info.device.address
        for event in update.events.values():
            key = event.device_key.key
            signal = format_event_dispatcher_name(address, key)
            async_dispatcher_send(hass, signal)

    return update


def format_event_dispatcher_name(address: str, key: str) -> str:
    """Format an event dispatcher name."""
    return f"{DOMAIN}_{address}_{key}"


class GoveeBLEBluetoothProcessorCoordinator(
    PassiveBluetoothProcessorCoordinator[SensorUpdate]
):
    """Define a govee ble Bluetooth Passive Update Processor Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        address: str,
        update_method: Callable[[BluetoothServiceInfoBleak], SensorUpdate],
        device_data: GoveeBluetoothDeviceData,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Govee BLE Bluetooth Passive Update Processor Coordinator."""
        self.model_info: ModelInfo | None = None
        # Active scanning is only needed for models that carry their payload in
        # the scan response; passively broadcasting models would otherwise be
        # scanned needlessly, costing fleet radio time and sensor battery.
        # When the model is not yet known, scan actively so a scan-response-only
        # model can still be discovered.
        mode = BluetoothScanningMode.ACTIVE
        scan_duration: float | None = None
        if device_type := entry.data.get(CONF_DEVICE_TYPE):
            self.model_info = model_info = get_model_info(device_type)
            if model_info.requires_active_scan:
                scan_duration = ACTIVE_SCAN_DURATION
            else:
                mode = BluetoothScanningMode.PASSIVE
        super().__init__(
            hass, logger, address, mode, update_method, scan_duration=scan_duration
        )
        self.device_data = device_data
        self.entry = entry

    def set_model_info(self, device_type: str) -> None:
        """Set the model info."""
        self.model_info = get_model_info(device_type)


class GoveeBLEPassiveBluetoothDataProcessor[_T](
    PassiveBluetoothDataProcessor[_T, SensorUpdate]
):
    """Define a govee-ble Bluetooth Passive Update Data Processor."""

    coordinator: GoveeBLEBluetoothProcessorCoordinator
