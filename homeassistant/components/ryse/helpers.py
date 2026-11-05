"""Helpers for the RYSE integration."""

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothScannerDevice,
    async_scanner_devices_by_address,
)
from homeassistant.core import HomeAssistant


def async_local_scanner_devices(
    hass: HomeAssistant, address: str
) -> list[BluetoothScannerDevice]:
    """Return local-adapter scanner devices for *address*, ignoring proxies.

    ``ryseble.pair()`` registers a BlueZ Agent1 on the Home Assistant host, which
    cannot answer pairing for a device reached through an ESPHome/Shelly proxy.
    """
    return [
        scanner_device
        for scanner_device in async_scanner_devices_by_address(
            hass, address, connectable=True
        )
        if not isinstance(scanner_device.scanner, BaseHaRemoteScanner)
    ]
