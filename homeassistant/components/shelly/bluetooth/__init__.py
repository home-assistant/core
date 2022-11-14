"""Bluetooth support for shelly."""
from __future__ import annotations

from typing import TypedDict, cast

from aioshelly.rpc_device import RpcDevice

from homeassistant.components.bluetooth import (
    HaBluetoothConnector,
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback
from homeassistant.helpers.device_registry import format_mac

from ..coordinator import ShellyRpcCoordinator
from .const import (
    BLE_CODE,
    BLE_SCAN_RESULT_EVENT,
    BLE_SCAN_RESULT_VERSION,
    BLE_SCRIPT_NAME,
    DEFAULT_DURATION_MS,
    DEFAULT_INTERVAL_MS,
    DEFAULT_WINDOW_MS,
    VAR_ACTIVE,
    VAR_DURATION_MS,
    VAR_EVENT_TYPE,
    VAR_INTERVAL_MS,
    VAR_VERSION,
    VAR_WINDOW_MS,
)
from .scanner import ShellyBLEScanner


class ShellyScript(TypedDict, total=False):
    """Shelly Script."""

    id: int
    name: str
    enable: bool
    running: bool


class ShellyScriptCode(TypedDict, total=False):
    """Shelly Script Code."""

    data: str


async def _async_get_scripts_by_name(device: RpcDevice) -> dict[str, int]:
    """Get scripts by name."""
    data = await device.call_rpc("Script.List")
    scripts: list[ShellyScript] = data["scripts"]
    return {script["name"]: script["id"] for script in scripts}


async def _async_start_scanner(
    device: RpcDevice,
    active: bool,
    event_type: str,
    data_version: int,
    interval_ms: int,
    window_ms: int,
    duration_ms: int,
) -> None:
    """Start scanner."""
    call_rpc = device.call_rpc

    script_name_to_id = await _async_get_scripts_by_name(device)
    if BLE_SCRIPT_NAME not in script_name_to_id:
        await call_rpc("Script.Create", {"name": BLE_SCRIPT_NAME})
        script_name_to_id = await _async_get_scripts_by_name(device)

    ble_script_id = script_name_to_id[BLE_SCRIPT_NAME]

    # Not using format strings here because the script
    # code contains curly braces
    code = (
        BLE_CODE.replace(VAR_ACTIVE, "true" if active else "false")
        .replace(VAR_EVENT_TYPE, event_type)
        .replace(VAR_VERSION, str(data_version))
        .replace(VAR_INTERVAL_MS, str(interval_ms))
        .replace(VAR_WINDOW_MS, str(window_ms))
        .replace(VAR_DURATION_MS, str(duration_ms))
    )

    code_response = cast(
        ShellyScriptCode, await call_rpc("Script.GetCode", {"id": ble_script_id})
    )
    if code_response["data"] != code:
        # Avoid writing the flash unless we actually need to
        # update the script
        await call_rpc("Script.Stop", {"id": ble_script_id})
        await call_rpc("Script.PutCode", {"id": ble_script_id, "code": code})

    await call_rpc("Script.Start", {"id": ble_script_id})


async def async_connect_scanner(
    hass: HomeAssistant,
    coordinator: ShellyRpcCoordinator,
    active: bool,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    device = coordinator.device
    source = format_mac(coordinator.mac).upper()
    new_info_callback = async_get_advertisement_callback(hass)
    connector = HaBluetoothConnector(
        # no active connections to shelly yet
        client=None,  # type: ignore[arg-type]
        source=source,
        can_connect=lambda: False,
    )
    scanner = ShellyBLEScanner(hass, source, new_info_callback, connector, False)
    unload_callbacks = [
        async_register_scanner(hass, scanner, False),
        scanner.async_setup(),
        coordinator.async_subscribe_events(scanner.async_on_event),
    ]
    await _async_start_scanner(
        device=device,
        active=active,
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
