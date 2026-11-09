"""Helpers for the RYSE integration."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from bleak.backends.device import BLEDevice
from habluetooth.wrappers import HaBleakClientWrapper

from homeassistant.components.bluetooth import (
    BaseHaRemoteScanner,
    BluetoothScannerDevice,
    async_scanner_devices_by_address,
)
from homeassistant.core import HomeAssistant

_GET_BEST_BACKEND = "_async_get_best_available_backend_and_device"


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


def async_best_local_scanner_device(
    hass: HomeAssistant,
    address: str,
    *,
    prefer: BLEDevice | None = None,
) -> BluetoothScannerDevice | None:
    """Return the best local-adapter sighting for *address*.

    BlueZ bonds are per adapter, so a paired path wins over a stronger RSSI
    on a different adapter. Remaining candidates use the Bluetooth manager's
    connection-path score (RSSI, slots, failures).
    """
    return best_local_scanner_device(
        async_local_scanner_devices(hass, address), prefer=prefer
    )


def best_local_scanner_device(
    devices: Sequence[BluetoothScannerDevice],
    *,
    prefer: BLEDevice | None = None,
) -> BluetoothScannerDevice | None:
    """Return the preferred local scanner device from *devices*."""
    if not devices:
        return None
    sorted_by_rssi = sorted(
        devices, key=lambda device: device.advertisement.rssi, reverse=True
    )
    rssi_diff = 0
    if len(sorted_by_rssi) > 1:
        rssi_diff = (
            sorted_by_rssi[0].advertisement.rssi - sorted_by_rssi[1].advertisement.rssi
        )
    return max(
        devices,
        key=lambda device: (
            _ble_device_is_paired(device.ble_device),
            prefer is not None and _same_ble_adapter(device.ble_device, prefer),
            device.score_connection_path(rssi_diff),
        ),
    )


class _PinnedBluetoothManager:
    """Expose only *ble_device*'s local adapter to HA's Bleak wrapper."""

    def __init__(self, manager: Any, ble_device: BLEDevice) -> None:
        self._manager = manager
        self._ble_device = ble_device
        self._address = ble_device.address.upper()

    def async_scanner_devices_by_address(
        self, address: str, connectable: bool
    ) -> list[BluetoothScannerDevice]:
        """Return scanner devices, limited to the pinned local adapter."""
        devices = self._manager.async_scanner_devices_by_address(address, connectable)
        if address.upper() != self._address:
            return devices
        return [
            scanner_device
            for scanner_device in devices
            if not isinstance(scanner_device.scanner, BaseHaRemoteScanner)
            and _same_ble_adapter(scanner_device.ble_device, self._ble_device)
        ]

    def __getattr__(self, name: str) -> Any:
        """Forward remaining Bluetooth manager API to the real manager."""
        return getattr(self._manager, name)


@contextmanager
def pin_ble_connection(ble_device: BLEDevice) -> Iterator[None]:
    """Restrict HA's Bleak wrapper to *ble_device*'s adapter for this address.

    HaBleakClientWrapper reselects a backend by address and can connect through
    a proxy even when the client was constructed with a local BLEDevice. RYSE
    pairing needs the host BlueZ adapter that holds the bond. The Bluetooth
    manager itself is a Cython type whose methods cannot be assigned, so the
    wrapper's backend selection is wrapped instead.
    """
    original = getattr(HaBleakClientWrapper, _GET_BEST_BACKEND)

    def _pinned(self: Any, manager: Any) -> Any:
        return original(self, _PinnedBluetoothManager(manager, ble_device))

    setattr(HaBleakClientWrapper, _GET_BEST_BACKEND, _pinned)
    try:
        yield
    finally:
        setattr(HaBleakClientWrapper, _GET_BEST_BACKEND, original)


def _ble_device_is_paired(device: BLEDevice) -> bool:
    """Return True when BlueZ reports this BLEDevice as paired."""
    details = device.details
    if not isinstance(details, dict):
        return False
    props = details.get("props")
    return isinstance(props, dict) and bool(props.get("Paired"))


def _same_ble_adapter(left: BLEDevice, right: BLEDevice) -> bool:
    """Return True when *left* and *right* are the same BlueZ adapter path."""
    if left is right:
        return True
    left_path = _bluez_device_path(left)
    right_path = _bluez_device_path(right)
    return left_path is not None and left_path == right_path


def _bluez_device_path(device: BLEDevice) -> str | None:
    """Return the BlueZ Device1 object path, if present."""
    details = device.details
    if not isinstance(details, dict):
        return None
    path = details.get("path")
    if isinstance(path, str):
        return path
    return None
