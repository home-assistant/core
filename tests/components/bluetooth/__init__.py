"""Tests for the Bluetooth integration."""


import time
from unittest.mock import patch

from bleak.backends.scanner import AdvertisementData, BLEDevice

from homeassistant.components.bluetooth import DOMAIN, SOURCE_LOCAL, models
from homeassistant.components.bluetooth.const import DEFAULT_ADDRESS
from homeassistant.components.bluetooth.manager import BluetoothManager
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


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


async def async_setup_with_default_adapter(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Bluetooth integration with a default adapter."""
    return await _async_setup_with_adapter(hass, DEFAULT_ADDRESS)


async def async_setup_with_one_adapter(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Bluetooth integration with one adapter."""
    return await _async_setup_with_adapter(hass, "00:00:00:00:00:01")


async def _async_setup_with_adapter(
    hass: HomeAssistant, address: str
) -> MockConfigEntry:
    """Set up the Bluetooth integration with any adapter."""
    entry = MockConfigEntry(domain="bluetooth", unique_id=address)
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return entry
