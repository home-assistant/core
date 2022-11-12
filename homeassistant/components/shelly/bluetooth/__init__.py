"""Bluetooth support for shelly."""
from __future__ import annotations

from typing import TypedDict

from aioshelly.rpc_device import RpcDevice

from homeassistant.components.bluetooth import (
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback
from homeassistant.helpers.device_registry import format_mac

from ..const import BLE_SCRIPT_NAME
from ..coordinator import ShellyRpcCoordinator
from .scanner import ShellyBLEScanner

BLE_SCRIPT_CODE = """
// Home Assistant BLE script v0.1.0
BLE.Scanner.Subscribe(function (ev, res) {
    if (ev === BLE.Scanner.SCAN_RESULT) {
        Shelly.emitEvent("ble.scan_result", [
            res.addr,
            res.rssi,
            btoa(res.advData),
            btoa(res.scanRsp)
        ]);
    }
});
BLE.Scanner.Start({
    duration_ms: -1,
    active: true,
    interval_ms: 320,
    window_ms: 30,
});
"""


class ShellyScript(TypedDict, total=False):
    """Shelly Script."""

    id: int
    name: str
    enable: bool
    running: bool


async def _async_get_scripts_by_name(device: RpcDevice) -> dict[str, int]:
    """Get scripts by name."""
    data = await device.call_rpc("Script.List")
    scripts: list[ShellyScript] = data["scripts"]
    return {script["name"]: script["id"] for script in scripts}


async def async_connect_scanner(
    hass: HomeAssistant,
    coordinator: ShellyRpcCoordinator,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    device = coordinator.device
    source = format_mac(coordinator.mac).upper()
    new_info_callback = async_get_advertisement_callback(hass)
    scanner = ShellyBLEScanner(hass, source, new_info_callback)
    unload_callbacks = [
        async_register_scanner(hass, scanner, False),
        scanner.async_setup(),
        coordinator.async_subscribe_ble_events(scanner.async_on_update),
    ]
    script_name_to_id = await _async_get_scripts_by_name(device)
    if BLE_SCRIPT_NAME not in script_name_to_id:
        await device.call_rpc("Script.Create", {"name": BLE_SCRIPT_NAME})
        script_name_to_id = await _async_get_scripts_by_name(device)

    ble_script_id = script_name_to_id[BLE_SCRIPT_NAME]
    await device.call_rpc("Script.Stop", {"id": ble_script_id})
    await device.call_rpc(
        "Script.PutCode", {"id": ble_script_id, "code": BLE_SCRIPT_CODE}
    )
    await device.call_rpc("Script.Start", {"id": ble_script_id})

    @hass_callback
    def _async_unload() -> None:
        for callback in unload_callbacks:
            callback()

    return _async_unload
