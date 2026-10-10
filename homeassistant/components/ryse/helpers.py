"""Helpers for the RYSE integration."""

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothScannerDevice,
    async_scanner_devices_by_address,
)
from homeassistant.core import HomeAssistant, callback

from .const import DATA_LOCAL_WAITERS


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


@callback
def async_cancel_local_waiter(hass: HomeAssistant, address: str) -> None:
    """Stop watching *address* for a local adapter."""
    waiters = hass.data.get(DATA_LOCAL_WAITERS)
    if not waiters:
        return
    if unsub := waiters.pop(address, None):
        unsub()
