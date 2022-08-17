"""Tests for the Bluetooth integration."""

import time

from bleak.backends.scanner import AdvertisementData, BLEDevice

from homeassistant.components.bluetooth import SOURCE_LOCAL, models
from homeassistant.components.bluetooth.manager import BluetoothManager


def _get_manager() -> BluetoothManager:
    """Return the underlying scanner that has been wrapped."""
    return models.MANAGER


def inject_advertisement(device: BLEDevice, adv: AdvertisementData) -> None:
    """Return the underlying scanner that has been wrapped."""
    return models.MANAGER.scanner_adv_received(
        device, adv, time.monotonic(), SOURCE_LOCAL
    )


def mock_discovered_devices(mock_discovered: list[BLEDevice]) -> None:
    """Return the underlying scanner that has been wrapped."""
    type(_get_manager()).discovered_devices = mock_discovered
