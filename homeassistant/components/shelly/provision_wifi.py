"""WiFi provisioning via BLE for Shelly devices."""

from __future__ import annotations

from typing import Any, cast

from aioshelly.common import ConnectionOptions
from aioshelly.rpc_device import RpcDevice
from bleak.backends.device import BLEDevice


async def async_scan_wifi_networks(ble_device: BLEDevice) -> list[dict[str, Any]]:
    """Scan for WiFi networks via BLE.

    Args:
        ble_device: BLE device to connect to

    Returns:
        List of WiFi networks with ssid, rssi, auth fields

    Raises:
        DeviceConnectionError: If connection to device fails
        RpcCallError: If RPC call fails

    """
    options = ConnectionOptions(ble_device=ble_device)
    device = await RpcDevice.create(
        aiohttp_session=None,
        ws_context=None,
        ip_or_options=options,
    )

    try:
        await device.initialize()
        # WiFi scan can take up to 20 seconds - use 30s timeout to be safe
        scan_result = await device.call_rpc("WiFi.Scan", timeout=30)
        return cast(list[dict[str, Any]], scan_result.get("results", []))
    finally:
        await device.shutdown()


async def async_provision_wifi(ble_device: BLEDevice, ssid: str, password: str) -> None:
    """Provision WiFi credentials to device via BLE.

    Args:
        ble_device: BLE device to connect to
        ssid: WiFi network SSID
        password: WiFi network password

    Raises:
        DeviceConnectionError: If connection to device fails
        RpcCallError: If RPC call fails

    """
    options = ConnectionOptions(ble_device=ble_device)
    device = await RpcDevice.create(
        aiohttp_session=None,
        ws_context=None,
        ip_or_options=options,
    )

    try:
        await device.initialize()
        await device.call_rpc(
            "WiFi.SetConfig",
            {
                "config": {
                    "sta": {
                        "ssid": ssid,
                        "pass": password,
                        "enable": True,
                    }
                }
            },
        )
    finally:
        await device.shutdown()
