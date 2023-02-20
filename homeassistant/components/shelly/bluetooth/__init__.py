"""Bluetooth support for shelly."""
from __future__ import annotations

from typing import TYPE_CHECKING

from aioshelly.ble import async_start_scanner
from aioshelly.ble.const import (
    BLE_SCAN_RESULT_EVENT,
    BLE_SCAN_RESULT_VERSION,
    DEFAULT_DURATION_MS,
    DEFAULT_INTERVAL_MS,
    DEFAULT_WINDOW_MS,
)

from homeassistant.components.bluetooth import (
    HaBluetoothConnector,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback
from homeassistant.helpers.device_registry import format_mac

from ..const import BLEScannerMode
from .scanner import ShellyBLEScanner

if TYPE_CHECKING:
    from ..coordinator import ShellyRpcCoordinator


async def async_connect_scanner(
    hass: HomeAssistant,
    coordinator: ShellyRpcCoordinator,
    scanner_mode: BLEScannerMode,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    device = coordinator.device
    entry = coordinator.entry
    source = format_mac(coordinator.mac).upper()
    new_info_callback = async_get_advertisement_callback(hass)
    connector = HaBluetoothConnector(
        # no active connections to shelly yet
        client=None,  # type: ignore[arg-type]
        source=source,
        can_connect=lambda: False,
    )
    scanner = ShellyBLEScanner(
        hass, source, entry.title, new_info_callback, connector, False
    )
    unload_callbacks = [
        async_register_scanner(hass, scanner, False),
        scanner.async_setup(),
        coordinator.async_subscribe_events(scanner.async_on_event),
    ]
    await async_start_scanner(
        device=device,
        active=scanner_mode == BLEScannerMode.ACTIVE,
        event_type=BLE_SCAN_RESULT_EVENT,
        data_version=BLE_SCAN_RESULT_VERSION,
        interval_ms=DEFAULT_INTERVAL_MS,
        window_ms=DEFAULT_WINDOW_MS,
        duration_ms=DEFAULT_DURATION_MS,
    )

    @hass_callback
    def _async_unload() -> None:
        for callback in unload_callbacks:
            callback()

    return _async_unload
