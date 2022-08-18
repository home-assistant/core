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
    """Inject an advertisement into the manager."""
    return inject_advertisement_with_source(device, adv, SOURCE_LOCAL)


def inject_advertisement_with_source(
    device: BLEDevice, adv: AdvertisementData, source: str
) -> None:
    """Inject an advertisement into the manager from a specific source."""
    inject_advertisement_with_time_and_source(device, adv, time.monotonic(), source)


def inject_advertisement_with_time_and_source(
    device: BLEDevice, adv: AdvertisementData, time: float, source: str
) -> None:
    """Inject an advertisement into the manager from a specific source at a time."""
    return _get_manager().scanner_adv_received(device, adv, time, source)


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
