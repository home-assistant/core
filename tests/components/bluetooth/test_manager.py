"""Tests for the Bluetooth integration manager."""

import time
from unittest.mock import patch

from bleak.backends.scanner import BLEDevice
from bluetooth_adapters import AdvertisementHistory
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import storage
from homeassistant.components.bluetooth.manager import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_loads
from homeassistant.setup import async_setup_component

from . import (
    FakeScanner,
    generate_advertisement_data,
    inject_advertisement_with_source,
    inject_advertisement_with_time_and_source,
    inject_advertisement_with_time_and_source_connectable,
)

from tests.common import load_fixture


@pytest.fixture
def register_hci0_scanner(hass: HomeAssistant) -> None:
    """Register an hci0 scanner."""
    hci0_scanner = FakeScanner(hass, "hci0", "hci0")
    cancel = bluetooth.async_register_scanner(hass, hci0_scanner, True)
    yield
    cancel()


@pytest.fixture
def register_hci1_scanner(hass: HomeAssistant) -> None:
    """Register an hci1 scanner."""
    hci1_scanner = FakeScanner(hass, "hci1", "hci1")
    cancel = bluetooth.async_register_scanner(hass, hci1_scanner, True)
    yield
    cancel()


async def test_advertisements_do_not_switch_adapters_for_no_reason(
    hass, enable_bluetooth, register_hci0_scanner, register_hci1_scanner
):
    """Test we only switch adapters when needed."""

    address = "44:44:33:11:23:12"

    switchbot_device_signal_100 = BLEDevice(address, "wohand_signal_100", rssi=-100)
    switchbot_adv_signal_100 = generate_advertisement_data(
        local_name="wohand_signal_100", service_uuids=[]
    )
    inject_advertisement_with_source(
        hass, switchbot_device_signal_100, switchbot_adv_signal_100, "hci0"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_signal_100
    )

    switchbot_device_signal_99 = BLEDevice(address, "wohand_signal_99", rssi=-99)
    switchbot_adv_signal_99 = generate_advertisement_data(
        local_name="wohand_signal_99", service_uuids=[]
    )
    inject_advertisement_with_source(
        hass, switchbot_device_signal_99, switchbot_adv_signal_99, "hci0"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_signal_99
    )

    switchbot_device_signal_98 = BLEDevice(address, "wohand_good_signal", rssi=-98)
    switchbot_adv_signal_98 = generate_advertisement_data(
        local_name="wohand_good_signal", service_uuids=[]
    )
    inject_advertisement_with_source(
        hass, switchbot_device_signal_98, switchbot_adv_signal_98, "hci1"
    )

    # should not switch to hci1
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_signal_99
    )


async def test_switching_adapters_based_on_rssi(
    hass, enable_bluetooth, register_hci0_scanner, register_hci1_scanner
):
    """Test switching adapters based on rssi."""

    address = "44:44:33:11:23:45"

    switchbot_device_poor_signal = BLEDevice(address, "wohand_poor_signal")
    switchbot_adv_poor_signal = generate_advertisement_data(
        local_name="wohand_poor_signal", service_uuids=[], rssi=-100
    )
    inject_advertisement_with_source(
        hass, switchbot_device_poor_signal, switchbot_adv_poor_signal, "hci0"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal
    )

    switchbot_device_good_signal = BLEDevice(address, "wohand_good_signal")
    switchbot_adv_good_signal = generate_advertisement_data(
        local_name="wohand_good_signal", service_uuids=[], rssi=-60
    )
    inject_advertisement_with_source(
        hass, switchbot_device_good_signal, switchbot_adv_good_signal, "hci1"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    inject_advertisement_with_source(
        hass, switchbot_device_good_signal, switchbot_adv_poor_signal, "hci0"
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    # We should not switch adapters unless the signal hits the threshold
    switchbot_device_similar_signal = BLEDevice(address, "wohand_similar_signal")
    switchbot_adv_similar_signal = generate_advertisement_data(
        local_name="wohand_similar_signal", service_uuids=[], rssi=-62
    )

    inject_advertisement_with_source(
        hass, switchbot_device_similar_signal, switchbot_adv_similar_signal, "hci0"
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )


async def test_switching_adapters_based_on_zero_rssi(
    hass, enable_bluetooth, register_hci0_scanner, register_hci1_scanner
):
    """Test switching adapters based on zero rssi."""

    address = "44:44:33:11:23:45"

    switchbot_device_no_rssi = BLEDevice(address, "wohand_poor_signal")
    switchbot_adv_no_rssi = generate_advertisement_data(
        local_name="wohand_no_rssi", service_uuids=[], rssi=0
    )
    inject_advertisement_with_source(
        hass, switchbot_device_no_rssi, switchbot_adv_no_rssi, "hci0"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_no_rssi
    )

    switchbot_device_good_signal = BLEDevice(address, "wohand_good_signal")
    switchbot_adv_good_signal = generate_advertisement_data(
        local_name="wohand_good_signal", service_uuids=[], rssi=-60
    )
    inject_advertisement_with_source(
        hass, switchbot_device_good_signal, switchbot_adv_good_signal, "hci1"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    inject_advertisement_with_source(
        hass, switchbot_device_good_signal, switchbot_adv_no_rssi, "hci0"
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    # We should not switch adapters unless the signal hits the threshold
    switchbot_device_similar_signal = BLEDevice(address, "wohand_similar_signal")
    switchbot_adv_similar_signal = generate_advertisement_data(
        local_name="wohand_similar_signal", service_uuids=[], rssi=-62
    )

    inject_advertisement_with_source(
        hass, switchbot_device_similar_signal, switchbot_adv_similar_signal, "hci0"
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )


async def test_switching_adapters_based_on_stale(
    hass, enable_bluetooth, register_hci0_scanner, register_hci1_scanner
):
    """Test switching adapters based on the previous advertisement being stale."""

    address = "44:44:33:11:23:41"
    start_time_monotonic = 50.0

    switchbot_device_poor_signal_hci0 = BLEDevice(address, "wohand_poor_signal_hci0")
    switchbot_adv_poor_signal_hci0 = generate_advertisement_data(
        local_name="wohand_poor_signal_hci0", service_uuids=[], rssi=-100
    )
    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device_poor_signal_hci0,
        switchbot_adv_poor_signal_hci0,
        start_time_monotonic,
        "hci0",
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal_hci0
    )

    switchbot_device_poor_signal_hci1 = BLEDevice(address, "wohand_poor_signal_hci1")
    switchbot_adv_poor_signal_hci1 = generate_advertisement_data(
        local_name="wohand_poor_signal_hci1", service_uuids=[], rssi=-99
    )
    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device_poor_signal_hci1,
        switchbot_adv_poor_signal_hci1,
        start_time_monotonic,
        "hci1",
    )

    # Should not switch adapters until the advertisement is stale
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal_hci0
    )

    # Should switch to hci1 since the previous advertisement is stale
    # even though the signal is poor because the device is now
    # likely unreachable via hci0
    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device_poor_signal_hci1,
        switchbot_adv_poor_signal_hci1,
        start_time_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1,
        "hci1",
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal_hci1
    )


async def test_restore_history_from_dbus(hass, one_adapter):
    """Test we can restore history from dbus."""
    address = "AA:BB:CC:CC:CC:FF"

    ble_device = BLEDevice(address, "name")
    history = {
        address: AdvertisementHistory(
            ble_device, generate_advertisement_data(local_name="name"), "hci0"
        )
    }

    with patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.history",
        history,
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    assert bluetooth.async_ble_device_from_address(hass, address) is ble_device


async def test_restore_history_from_dbus_and_remote_adapters(
    hass, one_adapter, hass_storage
):
    """Test we can restore history from dbus along with remote adapters."""
    address = "AA:BB:CC:CC:CC:FF"

    data = hass_storage[storage.REMOTE_SCANNER_STORAGE_KEY] = json_loads(
        load_fixture("bluetooth.remote_scanners", bluetooth.DOMAIN)
    )
    now = time.time()
    timestamps = data["data"]["atom-bluetooth-proxy-ceaac4"][
        "discovered_device_timestamps"
    ]
    for address in timestamps:
        timestamps[address] = now

    ble_device = BLEDevice(address, "name")
    history = {
        address: AdvertisementHistory(
            ble_device, generate_advertisement_data(local_name="name"), "hci0"
        )
    }

    with patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.history",
        history,
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    assert bluetooth.async_ble_device_from_address(hass, address) is not None
    assert (
        bluetooth.async_ble_device_from_address(hass, "EB:0B:36:35:6F:A4") is not None
    )


async def test_restore_history_from_dbus_and_corrupted_remote_adapters(
    hass, one_adapter, hass_storage
):
    """Test we can restore history from dbus when the remote adapters data is corrupted."""
    address = "AA:BB:CC:CC:CC:FF"

    data = hass_storage[storage.REMOTE_SCANNER_STORAGE_KEY] = json_loads(
        load_fixture("bluetooth.remote_scanners.corrupt", bluetooth.DOMAIN)
    )
    now = time.time()
    timestamps = data["data"]["atom-bluetooth-proxy-ceaac4"][
        "discovered_device_timestamps"
    ]
    for address in timestamps:
        timestamps[address] = now

    ble_device = BLEDevice(address, "name")
    history = {
        address: AdvertisementHistory(
            ble_device, generate_advertisement_data(local_name="name"), "hci0"
        )
    }

    with patch(
        "bluetooth_adapters.systems.linux.LinuxAdapters.history",
        history,
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    assert bluetooth.async_ble_device_from_address(hass, address) is not None
    assert bluetooth.async_ble_device_from_address(hass, "EB:0B:36:35:6F:A4") is None


async def test_switching_adapters_based_on_rssi_connectable_to_non_connectable(
    hass, enable_bluetooth, register_hci0_scanner, register_hci1_scanner
):
    """Test switching adapters based on rssi from connectable to non connectable."""

    address = "44:44:33:11:23:45"
    now = time.monotonic()
    switchbot_device_poor_signal = BLEDevice(address, "wohand_poor_signal")
    switchbot_adv_poor_signal = generate_advertisement_data(
        local_name="wohand_poor_signal", service_uuids=[], rssi=-100
    )
    inject_advertisement_with_time_and_source_connectable(
        hass, switchbot_device_poor_signal, switchbot_adv_poor_signal, now, "hci0", True
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address, False)
        is switchbot_device_poor_signal
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address, True)
        is switchbot_device_poor_signal
    )
    switchbot_device_good_signal = BLEDevice(address, "wohand_good_signal")
    switchbot_adv_good_signal = generate_advertisement_data(
        local_name="wohand_good_signal", service_uuids=[], rssi=-60
    )
    inject_advertisement_with_time_and_source_connectable(
        hass,
        switchbot_device_good_signal,
        switchbot_adv_good_signal,
        now,
        "hci1",
        False,
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address, False)
        is switchbot_device_good_signal
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address, True)
        is switchbot_device_poor_signal
    )
    inject_advertisement_with_time_and_source_connectable(
        hass,
        switchbot_device_good_signal,
        switchbot_adv_poor_signal,
        now,
        "hci0",
        False,
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address, False)
        is switchbot_device_good_signal
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address, True)
        is switchbot_device_poor_signal
    )
    switchbot_device_excellent_signal = BLEDevice(address, "wohand_excellent_signal")
    switchbot_adv_excellent_signal = generate_advertisement_data(
        local_name="wohand_excellent_signal", service_uuids=[], rssi=-25
    )

    inject_advertisement_with_time_and_source_connectable(
        hass,
        switchbot_device_excellent_signal,
        switchbot_adv_excellent_signal,
        now,
        "hci2",
        False,
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address, False)
        is switchbot_device_excellent_signal
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address, True)
        is switchbot_device_poor_signal
    )


async def test_connectable_advertisement_can_be_retrieved_with_best_path_is_non_connectable(
    hass, enable_bluetooth, register_hci0_scanner, register_hci1_scanner
):
    """Test we can still get a connectable BLEDevice when the best path is non-connectable.

    In this case the the device is closer to a non-connectable scanner, but the
    at least one connectable scanner has the device in range.
    """

    address = "44:44:33:11:23:45"
    now = time.monotonic()
    switchbot_device_good_signal = BLEDevice(address, "wohand_good_signal")
    switchbot_adv_good_signal = generate_advertisement_data(
        local_name="wohand_good_signal", service_uuids=[], rssi=-60
    )
    inject_advertisement_with_time_and_source_connectable(
        hass,
        switchbot_device_good_signal,
        switchbot_adv_good_signal,
        now,
        "hci1",
        False,
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address, False)
        is switchbot_device_good_signal
    )
    assert bluetooth.async_ble_device_from_address(hass, address, True) is None

    switchbot_device_poor_signal = BLEDevice(address, "wohand_poor_signal")
    switchbot_adv_poor_signal = generate_advertisement_data(
        local_name="wohand_poor_signal", service_uuids=[], rssi=-100
    )
    inject_advertisement_with_time_and_source_connectable(
        hass, switchbot_device_poor_signal, switchbot_adv_poor_signal, now, "hci0", True
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address, False)
        is switchbot_device_good_signal
    )
    assert (
        bluetooth.async_ble_device_from_address(hass, address, True)
        is switchbot_device_poor_signal
    )


async def test_switching_adapters_when_one_goes_away(
    hass, enable_bluetooth, register_hci0_scanner
):
    """Test switching adapters when one goes away."""
    cancel_hci2 = bluetooth.async_register_scanner(
        hass, FakeScanner(hass, "hci2", "hci2"), True
    )

    address = "44:44:33:11:23:45"

    switchbot_device_good_signal = BLEDevice(address, "wohand_good_signal")
    switchbot_adv_good_signal = generate_advertisement_data(
        local_name="wohand_good_signal", service_uuids=[], rssi=-60
    )
    inject_advertisement_with_source(
        hass, switchbot_device_good_signal, switchbot_adv_good_signal, "hci2"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    switchbot_device_poor_signal = BLEDevice(address, "wohand_poor_signal")
    switchbot_adv_poor_signal = generate_advertisement_data(
        local_name="wohand_poor_signal", service_uuids=[], rssi=-100
    )
    inject_advertisement_with_source(
        hass, switchbot_device_poor_signal, switchbot_adv_poor_signal, "hci0"
    )

    # We want to prefer the good signal when we have options
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    cancel_hci2()

    inject_advertisement_with_source(
        hass, switchbot_device_poor_signal, switchbot_adv_poor_signal, "hci0"
    )

    # Now that hci2 is gone, we should prefer the poor signal
    # since no poor signal is better than no signal
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal
    )


async def test_switching_adapters_when_one_stop_scanning(
    hass, enable_bluetooth, register_hci0_scanner
):
    """Test switching adapters when stops scanning."""
    hci2_scanner = FakeScanner(hass, "hci2", "hci2")
    cancel_hci2 = bluetooth.async_register_scanner(hass, hci2_scanner, True)

    address = "44:44:33:11:23:45"

    switchbot_device_good_signal = BLEDevice(address, "wohand_good_signal")
    switchbot_adv_good_signal = generate_advertisement_data(
        local_name="wohand_good_signal", service_uuids=[], rssi=-60
    )
    inject_advertisement_with_source(
        hass, switchbot_device_good_signal, switchbot_adv_good_signal, "hci2"
    )

    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    switchbot_device_poor_signal = BLEDevice(address, "wohand_poor_signal")
    switchbot_adv_poor_signal = generate_advertisement_data(
        local_name="wohand_poor_signal", service_uuids=[], rssi=-100
    )
    inject_advertisement_with_source(
        hass, switchbot_device_poor_signal, switchbot_adv_poor_signal, "hci0"
    )

    # We want to prefer the good signal when we have options
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_good_signal
    )

    hci2_scanner.scanning = False

    inject_advertisement_with_source(
        hass, switchbot_device_poor_signal, switchbot_adv_poor_signal, "hci0"
    )

    # Now that hci2 has stopped scanning, we should prefer the poor signal
    # since poor signal is better than no signal
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal
    )

    cancel_hci2()
