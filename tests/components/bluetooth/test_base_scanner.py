"""Tests for the Bluetooth base scanner models."""
from __future__ import annotations

from datetime import timedelta
import time
from typing import Any
from unittest.mock import patch

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    MONOTONIC_TIME,
    BaseHaRemoteScanner,
    HaBluetoothConnector,
    storage,
)
from homeassistant.components.bluetooth.advertisement_tracker import (
    TRACKER_BUFFERING_WOBBLE_SECONDS,
)
from homeassistant.components.bluetooth.const import (
    CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    UNAVAILABLE_TRACK_SECONDS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.json import json_loads

from . import (
    MockBleakClient,
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
)

from tests.common import async_fire_time_changed, load_fixture


async def test_remote_scanner(hass: HomeAssistant, enable_bluetooth: None) -> None:
    """Test the remote scanner base class merges advertisement_data."""
    manager = _get_manager()

    switchbot_device = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
    switchbot_device_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["050a021a-0000-1000-8000-00805f9b34fb"],
        service_data={"050a021a-0000-1000-8000-00805f9b34fb": b"\n\xff"},
        manufacturer_data={1: b"\x01"},
        rssi=-100,
    )
    switchbot_device_2 = generate_ble_device(
        "44:44:33:11:23:45",
        "w",
        {},
        rssi=-100,
    )
    switchbot_device_adv_2 = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["00000001-0000-1000-8000-00805f9b34fb"],
        service_data={"00000001-0000-1000-8000-00805f9b34fb": b"\n\xff"},
        manufacturer_data={1: b"\x01", 2: b"\x02"},
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
                {"scanner_specific_data": "test"},
                MONOTONIC_TIME(),
            )

    new_info_callback = manager.scanner_adv_received
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeScanner(hass, "esp32", "esp32", new_info_callback, connector, True)
    unsetup = scanner.async_setup()
    cancel = manager.async_register_scanner(scanner, True)

    scanner.inject_advertisement(switchbot_device, switchbot_device_adv)

    data = scanner.discovered_devices_and_advertisement_data
    discovered_device, discovered_adv_data = data[switchbot_device.address]
    assert discovered_device.address == switchbot_device.address
    assert discovered_device.name == switchbot_device.name
    assert (
        discovered_adv_data.manufacturer_data == switchbot_device_adv.manufacturer_data
    )
    assert discovered_adv_data.service_data == switchbot_device_adv.service_data
    assert discovered_adv_data.service_uuids == switchbot_device_adv.service_uuids
    scanner.inject_advertisement(switchbot_device_2, switchbot_device_adv_2)

    data = scanner.discovered_devices_and_advertisement_data
    discovered_device, discovered_adv_data = data[switchbot_device.address]
    assert discovered_device.address == switchbot_device.address
    assert discovered_device.name == switchbot_device.name
    assert discovered_adv_data.manufacturer_data == {1: b"\x01", 2: b"\x02"}
    assert discovered_adv_data.service_data == {
        "050a021a-0000-1000-8000-00805f9b34fb": b"\n\xff",
        "00000001-0000-1000-8000-00805f9b34fb": b"\n\xff",
    }
    assert set(discovered_adv_data.service_uuids) == {
        "050a021a-0000-1000-8000-00805f9b34fb",
        "00000001-0000-1000-8000-00805f9b34fb",
    }

    cancel()
    unsetup()


async def test_remote_scanner_expires_connectable(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test the remote scanner expires stale connectable data."""
    manager = _get_manager()

    switchbot_device = generate_ble_device(
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
                {"scanner_specific_data": "test"},
                MONOTONIC_TIME(),
            )

    new_info_callback = manager.scanner_adv_received
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeScanner(hass, "esp32", "esp32", new_info_callback, connector, True)
    unsetup = scanner.async_setup()
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
    unsetup()


async def test_remote_scanner_expires_non_connectable(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test the remote scanner expires stale non connectable data."""
    manager = _get_manager()

    switchbot_device = generate_ble_device(
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
                {"scanner_specific_data": "test"},
                MONOTONIC_TIME(),
            )

    new_info_callback = manager.scanner_adv_received
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeScanner(hass, "esp32", "esp32", new_info_callback, connector, False)
    unsetup = scanner.async_setup()
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

    # The connectable timeout is used for all devices
    # as the manager takes care of availability and the scanner
    # if only concerned about making a connection
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

    assert len(scanner.discovered_devices) == 0
    assert len(scanner.discovered_devices_and_advertisement_data) == 0

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
    unsetup()


async def test_base_scanner_connecting_behavior(
    hass: HomeAssistant, enable_bluetooth: None
) -> None:
    """Test that the default behavior is to mark the scanner as not scanning when connecting."""
    manager = _get_manager()

    switchbot_device = generate_ble_device(
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
                {"scanner_specific_data": "test"},
                MONOTONIC_TIME(),
            )

    new_info_callback = manager.scanner_adv_received
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeScanner(hass, "esp32", "esp32", new_info_callback, connector, False)
    unsetup = scanner.async_setup()
    cancel = manager.async_register_scanner(scanner, True)

    with scanner.connecting():
        assert scanner.scanning is False

        # We should still accept new advertisements while connecting
        # since advertisements are delivered asynchronously and
        # we don't want to miss any even when we are willing to
        # accept advertisements from another scanner in the brief window
        # between when we start connecting and when we stop scanning
        scanner.inject_advertisement(switchbot_device, switchbot_device_adv)

    devices = scanner.discovered_devices
    assert len(scanner.discovered_devices) == 1
    assert len(scanner.discovered_devices_and_advertisement_data) == 1
    assert devices[0].name == "wohand"

    cancel()
    unsetup()


async def test_restore_history_remote_adapter(
    hass: HomeAssistant, hass_storage: dict[str, Any], disable_new_discovery_flows
) -> None:
    """Test we can restore history for a remote adapter."""

    data = hass_storage[storage.REMOTE_SCANNER_STORAGE_KEY] = json_loads(
        load_fixture("bluetooth.remote_scanners", bluetooth.DOMAIN)
    )
    now = time.time()
    timestamps = data["data"]["atom-bluetooth-proxy-ceaac4"][
        "discovered_device_timestamps"
    ]
    for address in timestamps:
        if address != "E3:A5:63:3E:5E:23":
            timestamps[address] = now

    with patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.history",
        {},
    ), patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.refresh",
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = BaseHaRemoteScanner(
        hass,
        "atom-bluetooth-proxy-ceaac4",
        "atom-bluetooth-proxy-ceaac4",
        lambda adv: None,
        connector,
        True,
    )
    unsetup = scanner.async_setup()
    cancel = _get_manager().async_register_scanner(scanner, True)

    assert "EB:0B:36:35:6F:A4" in scanner.discovered_devices_and_advertisement_data
    assert "E3:A5:63:3E:5E:23" not in scanner.discovered_devices_and_advertisement_data
    cancel()
    unsetup()

    scanner = BaseHaRemoteScanner(
        hass,
        "atom-bluetooth-proxy-ceaac4",
        "atom-bluetooth-proxy-ceaac4",
        lambda adv: None,
        connector,
        True,
    )
    unsetup = scanner.async_setup()
    cancel = _get_manager().async_register_scanner(scanner, True)
    assert "EB:0B:36:35:6F:A4" in scanner.discovered_devices_and_advertisement_data
    assert "E3:A5:63:3E:5E:23" not in scanner.discovered_devices_and_advertisement_data

    cancel()
    unsetup()


async def test_device_with_ten_minute_advertising_interval(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, enable_bluetooth: None
) -> None:
    """Test a device with a 10 minute advertising interval."""
    manager = _get_manager()

    bparasite_device = generate_ble_device(
        "44:44:33:11:23:45",
        "bparasite",
        {},
        rssi=-100,
    )
    bparasite_device_adv = generate_advertisement_data(
        local_name="bparasite",
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
                {"scanner_specific_data": "test"},
                MONOTONIC_TIME(),
            )

    new_info_callback = manager.scanner_adv_received
    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    scanner = FakeScanner(hass, "esp32", "esp32", new_info_callback, connector, False)
    unsetup = scanner.async_setup()
    cancel = manager.async_register_scanner(scanner, True)

    monotonic_now = time.monotonic()
    new_time = monotonic_now
    bparasite_device_went_unavailable = False

    @callback
    def _bparasite_device_unavailable_callback(_address: str) -> None:
        """Barasite device unavailable callback."""
        nonlocal bparasite_device_went_unavailable
        bparasite_device_went_unavailable = True

    advertising_interval = 60 * 10

    bparasite_device_unavailable_cancel = bluetooth.async_track_unavailable(
        hass,
        _bparasite_device_unavailable_callback,
        bparasite_device.address,
        connectable=False,
    )

    with patch(
        "homeassistant.components.bluetooth.base_scanner.MONOTONIC_TIME",
        return_value=new_time,
    ):
        scanner.inject_advertisement(bparasite_device, bparasite_device_adv)

    original_device = scanner.discovered_devices_and_advertisement_data[
        bparasite_device.address
    ][0]
    assert original_device is not bparasite_device

    for _ in range(1, 20):
        new_time += advertising_interval
        with patch(
            "homeassistant.components.bluetooth.base_scanner.MONOTONIC_TIME",
            return_value=new_time,
        ):
            scanner.inject_advertisement(bparasite_device, bparasite_device_adv)

    # Make sure the BLEDevice object gets updated
    # and not replaced
    assert (
        scanner.discovered_devices_and_advertisement_data[bparasite_device.address][0]
        is original_device
    )

    future_time = new_time
    assert (
        bluetooth.async_address_present(hass, bparasite_device.address, False) is True
    )
    assert bparasite_device_went_unavailable is False
    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=new_time,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=future_time))
        await hass.async_block_till_done()

    assert bparasite_device_went_unavailable is False

    missed_advertisement_future_time = (
        future_time + advertising_interval + TRACKER_BUFFERING_WOBBLE_SECONDS + 1
    )

    with patch(
        "homeassistant.components.bluetooth.manager.MONOTONIC_TIME",
        return_value=missed_advertisement_future_time,
    ), patch(
        "homeassistant.components.bluetooth.base_scanner.MONOTONIC_TIME",
        return_value=missed_advertisement_future_time,
    ):
        # Fire once for the scanner to expire the device
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()
        # Fire again for the manager to expire the device
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=missed_advertisement_future_time)
        )
        await hass.async_block_till_done()

    assert (
        bluetooth.async_address_present(hass, bparasite_device.address, False) is False
    )
    assert bparasite_device_went_unavailable is True
    bparasite_device_unavailable_cancel()

    cancel()
    unsetup()
