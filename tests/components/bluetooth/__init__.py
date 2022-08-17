"""Tests for the Bluetooth integration."""


import time
from unittest.mock import patch

from bleak.backends.scanner import AdvertisementData, BLEDevice

from homeassistant.components.bluetooth import SOURCE_LOCAL, models
from homeassistant.components.bluetooth.manager import BluetoothManager


def _get_manager() -> BluetoothManager:
    """Return the bluetooth manager."""
    return models.MANAGER


def inject_advertisement(device: BLEDevice, adv: AdvertisementData) -> None:
    """Return the underlying scanner that has been wrapped."""
    return _get_manager().scanner_adv_received(
        device, adv, time.monotonic(), SOURCE_LOCAL
    )


def patch_all_discovered_devices(mock_discovered: list[BLEDevice]) -> None:
    """Mock all the discovered devices from all the scanners."""
    manager = _get_manager()
    return patch.object(
        manager, "async_all_discovered_devices", return_value=mock_discovered
    )


def patch_discovered_devices(mock_discovered: list[BLEDevice]) -> None:
    """Mock the combined best path to discovered devices from all the scanners."""
    manager = _get_manager()
    return patch.object(
        manager, "async_discovered_devices", return_value=mock_discovered
    )
