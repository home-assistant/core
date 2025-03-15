"""Bluetooth support for shelly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aioshelly.ble import async_start_scanner, create_scanner
from aioshelly.ble.const import BLE_SCAN_RESULT_EVENT, BLE_SCAN_RESULT_VERSION

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    async_register_scanner,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback

from ..const import BLEScannerMode

if TYPE_CHECKING:
    from ..coordinator import ShellyRpcCoordinator

BLE_SCANNER_MODE_TO_BLUETOOTH_SCANNING_MODE = {
    BLEScannerMode.PASSIVE: BluetoothScanningMode.PASSIVE,
    BLEScannerMode.ACTIVE: BluetoothScanningMode.ACTIVE,
}


async def async_connect_scanner(
    hass: HomeAssistant,
    coordinator: ShellyRpcCoordinator,
    scanner_mode: BLEScannerMode,
    device_id: str,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    device = coordinator.device
    entry = coordinator.config_entry
    bluetooth_scanning_mode = BLE_SCANNER_MODE_TO_BLUETOOTH_SCANNING_MODE[scanner_mode]
    scanner = create_scanner(
        coordinator.bluetooth_source,
        entry.title,
        requested_mode=bluetooth_scanning_mode,
        current_mode=bluetooth_scanning_mode,
    )
    unload_callbacks = [
        async_register_scanner(
            hass,
            scanner,
            source_domain=entry.domain,
            source_model=coordinator.model,
            source_config_entry_id=entry.entry_id,
            source_device_id=device_id,
        ),
        scanner.async_setup(),
        coordinator.async_subscribe_events(scanner.async_on_event),
    ]
    await async_start_scanner(
        device=device,
        active=scanner_mode == BLEScannerMode.ACTIVE,
        event_type=BLE_SCAN_RESULT_EVENT,
        data_version=BLE_SCAN_RESULT_VERSION,
    )

    @hass_callback
    def _async_unload() -> None:
        for callback in unload_callbacks:
            callback()

    return _async_unload
