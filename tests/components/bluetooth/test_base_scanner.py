"""Tests for the Bluetooth base scanner models."""
from __future__ import annotations

from datetime import timedelta
import time
from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components.bluetooth import BaseHaRemoteScanner, HaBluetoothConnector
from homeassistant.components.bluetooth.const import (
    CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
import homeassistant.util.dt as dt_util

from . import MockBleakClient, _get_manager, generate_advertisement_data

from tests.common import async_fire_time_changed


async def test_remote_scanner_expires_connectable(hass):
    """Test the remote scanner expires stale connectable data."""
    manager = _get_manager()

    switchbot_device = BLEDevice(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
    switchbot_device_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-100,
    )

    class FakeScanner(BaseHaRemoteScanner):
        def inject_advertisement(
            self, device: BLEDevice, advertisement_data: AdvertisementData
        ) -> None:
            """Inject an advertisement."""
            self._async_on_advertisement(
                device.address,
                advertisement_data.rssi,
                device.name,
                advertisement_data.service_uuids,
                advertisement_data.service_data,
                advertisement_data.manufacturer_data,
                advertisement_data.tx_power,
            )

    new_info_callback = manager.scanner_adv_received
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeScanner(hass, "esp32", new_info_callback, connector, True)
    scanner.async_setup()
    cancel = manager.async_register_scanner(scanner, True)

    start_time_monotonic = time.monotonic()
    scanner.inject_advertisement(switchbot_device, switchbot_device_adv)

    devices = scanner.discovered_devices
    assert len(scanner.discovered_devices) == 1
    assert len(scanner.discovered_devices_and_advertisement_data) == 1
    assert devices[0].name == "wohand"

    expire_monotonic = (
        start_time_monotonic
        + CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        + 1
    )
    expire_utc = dt_util.utcnow() + timedelta(
        seconds=CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    )
    with patch(
        "homeassistant.components.bluetooth.base_scanner.MONOTONIC_TIME",
        return_value=expire_monotonic,
    ):
        async_fire_time_changed(hass, expire_utc)
        await hass.async_block_till_done()

    devices = scanner.discovered_devices
    assert len(scanner.discovered_devices) == 0
    assert len(scanner.discovered_devices_and_advertisement_data) == 0

    cancel()


async def test_remote_scanner_expires_non_connectable(hass):
    """Test the remote scanner expires stale non connectable data."""
    manager = _get_manager()

    switchbot_device = BLEDevice(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
    switchbot_device_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=[],
        manufacturer_data={1: b"\x01"},
        rssi=-100,
    )

    class FakeScanner(BaseHaRemoteScanner):
        def inject_advertisement(
            self, device: BLEDevice, advertisement_data: AdvertisementData
        ) -> None:
            """Inject an advertisement."""
            self._async_on_advertisement(
                device.address,
                advertisement_data.rssi,
                device.name,
                advertisement_data.service_uuids,
                advertisement_data.service_data,
                advertisement_data.manufacturer_data,
                advertisement_data.tx_power,
            )

    new_info_callback = manager.scanner_adv_received
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeScanner(hass, "esp32", new_info_callback, connector, False)
    scanner.async_setup()
    cancel = manager.async_register_scanner(scanner, True)

    start_time_monotonic = time.monotonic()
    scanner.inject_advertisement(switchbot_device, switchbot_device_adv)

    devices = scanner.discovered_devices
    assert len(scanner.discovered_devices) == 1
    assert len(scanner.discovered_devices_and_advertisement_data) == 1
    assert devices[0].name == "wohand"

    assert (
        FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        > CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
    )

    # The connectable timeout is not used for non connectable devices
    expire_monotonic = (
        start_time_monotonic
        + CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        + 1
    )
    expire_utc = dt_util.utcnow() + timedelta(
        seconds=CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    )
    with patch(
        "homeassistant.components.bluetooth.base_scanner.MONOTONIC_TIME",
        return_value=expire_monotonic,
    ):
        async_fire_time_changed(hass, expire_utc)
        await hass.async_block_till_done()

    assert len(scanner.discovered_devices) == 1
    assert len(scanner.discovered_devices_and_advertisement_data) == 1

    # The non connectable timeout is used for non connectable devices
    # which is always longer than the connectable timeout
    expire_monotonic = (
        start_time_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    )
    expire_utc = dt_util.utcnow() + timedelta(
        seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    )
    with patch(
        "homeassistant.components.bluetooth.base_scanner.MONOTONIC_TIME",
        return_value=expire_monotonic,
    ):
        async_fire_time_changed(hass, expire_utc)
        await hass.async_block_till_done()

    assert len(scanner.discovered_devices) == 0
    assert len(scanner.discovered_devices_and_advertisement_data) == 0

    cancel()
