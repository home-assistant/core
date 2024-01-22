"""Tests for the Bluetooth integration manager."""
from collections.abc import Generator
from datetime import timedelta
import time
from typing import Any
from unittest.mock import patch

from bleak.backends.scanner import AdvertisementData, BLEDevice
from bluetooth_adapters import AdvertisementHistory
from habluetooth.advertisement_tracker import TRACKER_BUFFERING_WOBBLE_SECONDS
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    MONOTONIC_TIME,
    BaseHaRemoteScanner,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfo,
    BluetoothServiceInfoBleak,
    HaBluetoothConnector,
    async_ble_device_from_address,
    async_get_fallback_availability_interval,
    async_get_learned_advertising_interval,
    async_scanner_count,
    async_set_fallback_availability_interval,
    async_track_unavailable,
    storage,
)
from homeassistant.components.bluetooth.const import (
    SOURCE_LOCAL,
    UNAVAILABLE_TRACK_SECONDS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.json import json_loads

from . import (
    FakeScanner,
    MockBleakClient,
    _get_manager,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_source,
    inject_advertisement_with_time_and_source,
    inject_advertisement_with_time_and_source_connectable,
    patch_bluetooth_time,
)

from tests.common import async_fire_time_changed, load_fixture


@pytest.fixture
def register_hci0_scanner(hass: HomeAssistant) -> Generator[None, None, None]:
    """Register an hci0 scanner."""
    hci0_scanner = FakeScanner("hci0", "hci0")
    cancel = bluetooth.async_register_scanner(hass, hci0_scanner)
    yield
    cancel()


@pytest.fixture
def register_hci1_scanner(hass: HomeAssistant) -> Generator[None, None, None]:
    """Register an hci1 scanner."""
    hci1_scanner = FakeScanner("hci1", "hci1")
    cancel = bluetooth.async_register_scanner(hass, hci1_scanner)
    yield
    cancel()


async def test_advertisements_do_not_switch_adapters_for_no_reason(
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
) -> None:
    """Test we only switch adapters when needed."""

    address = "44:44:33:11:23:12"

    switchbot_device_signal_100 = generate_ble_device(
        address, "wohand_signal_100", rssi=-100
    )
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

    switchbot_device_signal_99 = generate_ble_device(
        address, "wohand_signal_99", rssi=-99
    )
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

    switchbot_device_signal_98 = generate_ble_device(
        address, "wohand_good_signal", rssi=-98
    )
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
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
) -> None:
    """Test switching adapters based on rssi."""

    address = "44:44:33:11:23:45"

    switchbot_device_poor_signal = generate_ble_device(address, "wohand_poor_signal")
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

    switchbot_device_good_signal = generate_ble_device(address, "wohand_good_signal")
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
    switchbot_device_similar_signal = generate_ble_device(
        address, "wohand_similar_signal"
    )
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
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
) -> None:
    """Test switching adapters based on zero rssi."""

    address = "44:44:33:11:23:45"

    switchbot_device_no_rssi = generate_ble_device(address, "wohand_poor_signal")
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

    switchbot_device_good_signal = generate_ble_device(address, "wohand_good_signal")
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
    switchbot_device_similar_signal = generate_ble_device(
        address, "wohand_similar_signal"
    )
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
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
) -> None:
    """Test switching adapters based on the previous advertisement being stale."""

    address = "44:44:33:11:23:41"
    start_time_monotonic = 50.0

    switchbot_device_poor_signal_hci0 = generate_ble_device(
        address, "wohand_poor_signal_hci0"
    )
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

    switchbot_device_poor_signal_hci1 = generate_ble_device(
        address, "wohand_poor_signal_hci1"
    )
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


async def test_switching_adapters_based_on_stale_with_discovered_interval(
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
) -> None:
    """Test switching with discovered interval."""

    address = "44:44:33:11:23:41"
    start_time_monotonic = 50.0

    switchbot_device_poor_signal_hci0 = generate_ble_device(
        address, "wohand_poor_signal_hci0"
    )
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

    bluetooth.async_set_fallback_availability_interval(hass, address, 10)

    switchbot_device_poor_signal_hci1 = generate_ble_device(
        address, "wohand_poor_signal_hci1"
    )
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

    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device_poor_signal_hci1,
        switchbot_adv_poor_signal_hci1,
        start_time_monotonic + 10 + 1,
        "hci1",
    )

    # Should not switch yet since we are not within the
    # wobble period
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal_hci0
    )

    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device_poor_signal_hci1,
        switchbot_adv_poor_signal_hci1,
        start_time_monotonic + 10 + TRACKER_BUFFERING_WOBBLE_SECONDS + 1,
        "hci1",
    )
    # Should switch to hci1 since the previous advertisement is stale
    # even though the signal is poor because the device is now
    # likely unreachable via hci0
    assert (
        bluetooth.async_ble_device_from_address(hass, address)
        is switchbot_device_poor_signal_hci1
    )


async def test_restore_history_from_dbus(
    hass: HomeAssistant, one_adapter: None, disable_new_discovery_flows
) -> None:
    """Test we can restore history from dbus."""
    address = "AA:BB:CC:CC:CC:FF"

    ble_device = generate_ble_device(address, "name")
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
    hass: HomeAssistant,
    one_adapter: None,
    hass_storage: dict[str, Any],
    disable_new_discovery_flows,
) -> None:
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

    ble_device = generate_ble_device(address, "name")
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
    assert disable_new_discovery_flows.call_count > 1


async def test_restore_history_from_dbus_and_corrupted_remote_adapters(
    hass: HomeAssistant,
    one_adapter: None,
    hass_storage: dict[str, Any],
    disable_new_discovery_flows,
) -> None:
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

    ble_device = generate_ble_device(address, "name")
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
    assert disable_new_discovery_flows.call_count >= 1


async def test_switching_adapters_based_on_rssi_connectable_to_non_connectable(
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
) -> None:
    """Test switching adapters based on rssi from connectable to non connectable."""

    address = "44:44:33:11:23:45"
    now = time.monotonic()
    switchbot_device_poor_signal = generate_ble_device(address, "wohand_poor_signal")
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
    switchbot_device_good_signal = generate_ble_device(address, "wohand_good_signal")
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
    switchbot_device_excellent_signal = generate_ble_device(
        address, "wohand_excellent_signal"
    )
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
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
) -> None:
    """Test we can still get a connectable BLEDevice when the best path is non-connectable.

    In this case the the device is closer to a non-connectable scanner, but the
    at least one connectable scanner has the device in range.
    """

    address = "44:44:33:11:23:45"
    now = time.monotonic()
    switchbot_device_good_signal = generate_ble_device(address, "wohand_good_signal")
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

    switchbot_device_poor_signal = generate_ble_device(address, "wohand_poor_signal")
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
    hass: HomeAssistant, enable_bluetooth: None, register_hci0_scanner: None
) -> None:
    """Test switching adapters when one goes away."""
    cancel_hci2 = bluetooth.async_register_scanner(hass, FakeScanner("hci2", "hci2"))

    address = "44:44:33:11:23:45"

    switchbot_device_good_signal = generate_ble_device(address, "wohand_good_signal")
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

    switchbot_device_poor_signal = generate_ble_device(address, "wohand_poor_signal")
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
    hass: HomeAssistant, enable_bluetooth: None, register_hci0_scanner: None
) -> None:
    """Test switching adapters when stops scanning."""
    hci2_scanner = FakeScanner("hci2", "hci2")
    cancel_hci2 = bluetooth.async_register_scanner(hass, hci2_scanner)

    address = "44:44:33:11:23:45"

    switchbot_device_good_signal = generate_ble_device(address, "wohand_good_signal")
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

    switchbot_device_poor_signal = generate_ble_device(address, "wohand_poor_signal")
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


async def test_goes_unavailable_connectable_only_and_recovers(
    hass: HomeAssistant, mock_bluetooth_adapters: None
) -> None:
    """Test all connectable scanners go unavailable, and than recover when there is a non-connectable scanner."""
    assert await async_setup_component(hass, bluetooth.DOMAIN, {})
    await hass.async_block_till_done()

    assert async_scanner_count(hass, connectable=True) == 0
    assert async_scanner_count(hass, connectable=False) == 0
    switchbot_device_connectable = generate_ble_device(
        "44:44:33:11:23:45",
        "wohand",
        {},
        rssi=-100,
    )
    switchbot_device_non_connectable = generate_ble_device(
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
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))

    cancel = bluetooth.async_register_callback(
        hass,
        _fake_subscriber,
        {"address": "44:44:33:11:23:45", "connectable": True},
        BluetoothScanningMode.ACTIVE,
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

    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    connectable_scanner = FakeScanner(
        "connectable",
        "connectable",
        connector,
        True,
    )
    unsetup_connectable_scanner = connectable_scanner.async_setup()
    cancel_connectable_scanner = _get_manager().async_register_scanner(
        connectable_scanner
    )
    connectable_scanner.inject_advertisement(
        switchbot_device_connectable, switchbot_device_adv
    )
    assert async_ble_device_from_address(hass, "44:44:33:11:23:45") is not None
    assert async_scanner_count(hass, connectable=True) == 1
    assert len(callbacks) == 1

    assert (
        "44:44:33:11:23:45"
        in connectable_scanner.discovered_devices_and_advertisement_data
    )

    not_connectable_scanner = FakeScanner(
        "not_connectable",
        "not_connectable",
        connector,
        False,
    )
    unsetup_not_connectable_scanner = not_connectable_scanner.async_setup()
    cancel_not_connectable_scanner = _get_manager().async_register_scanner(
        not_connectable_scanner
    )
    not_connectable_scanner.inject_advertisement(
        switchbot_device_non_connectable, switchbot_device_adv
    )
    assert async_scanner_count(hass, connectable=True) == 1
    assert async_scanner_count(hass, connectable=False) == 2

    assert (
        "44:44:33:11:23:45"
        in not_connectable_scanner.discovered_devices_and_advertisement_data
    )

    unavailable_callbacks: list[BluetoothServiceInfoBleak] = []

    @callback
    def _unavailable_callback(service_info: BluetoothServiceInfoBleak) -> None:
        """Wrong device unavailable callback."""
        nonlocal unavailable_callbacks
        unavailable_callbacks.append(service_info.address)

    cancel_unavailable = async_track_unavailable(
        hass,
        _unavailable_callback,
        switchbot_device_connectable.address,
        connectable=True,
    )

    assert async_scanner_count(hass, connectable=True) == 1
    cancel_connectable_scanner()
    unsetup_connectable_scanner()
    assert async_scanner_count(hass, connectable=True) == 0
    assert async_scanner_count(hass, connectable=False) == 1

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
    )
    await hass.async_block_till_done()
    assert "44:44:33:11:23:45" in unavailable_callbacks
    cancel_unavailable()

    connectable_scanner_2 = FakeScanner(
        "connectable",
        "connectable",
        connector,
        True,
    )
    unsetup_connectable_scanner_2 = connectable_scanner_2.async_setup()
    cancel_connectable_scanner_2 = _get_manager().async_register_scanner(
        connectable_scanner
    )
    connectable_scanner_2.inject_advertisement(
        switchbot_device_connectable, switchbot_device_adv
    )
    assert (
        "44:44:33:11:23:45"
        in connectable_scanner_2.discovered_devices_and_advertisement_data
    )

    # We should get another callback to make the device available again
    assert len(callbacks) == 2

    cancel()
    cancel_connectable_scanner_2()
    unsetup_connectable_scanner_2()
    cancel_not_connectable_scanner()
    unsetup_not_connectable_scanner()


async def test_goes_unavailable_dismisses_discovery_and_makes_discoverable(
    hass: HomeAssistant, mock_bluetooth_adapters: None
) -> None:
    """Test that unavailable will dismiss any active discoveries and make device discoverable again."""
    mock_bt = [
        {
            "domain": "switchbot",
            "service_data_uuid": "050a021a-0000-1000-8000-00805f9b34fb",
            "connectable": False,
        },
    ]
    with patch(
        "homeassistant.components.bluetooth.async_get_bluetooth", return_value=mock_bt
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    assert async_scanner_count(hass, connectable=False) == 0
    switchbot_device_non_connectable = generate_ble_device(
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
    callbacks = []

    def _fake_subscriber(
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Fake subscriber for the BleakScanner."""
        callbacks.append((service_info, change))

    cancel = bluetooth.async_register_callback(
        hass,
        _fake_subscriber,
        {"address": "44:44:33:11:23:45", "connectable": False},
        BluetoothScanningMode.ACTIVE,
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

        def clear_all_devices(self) -> None:
            """Clear all devices."""
            self._discovered_device_advertisement_datas.clear()
            self._discovered_device_timestamps.clear()
            self._previous_service_info.clear()

    connector = (
        HaBluetoothConnector(MockBleakClient, "mock_bleak_client", lambda: False),
    )
    non_connectable_scanner = FakeScanner(
        "connectable",
        "connectable",
        connector,
        False,
    )
    unsetup_connectable_scanner = non_connectable_scanner.async_setup()
    cancel_connectable_scanner = _get_manager().async_register_scanner(
        non_connectable_scanner
    )
    with patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        non_connectable_scanner.inject_advertisement(
            switchbot_device_non_connectable, switchbot_device_adv
        )
        await hass.async_block_till_done()

    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "switchbot"

    assert async_ble_device_from_address(hass, "44:44:33:11:23:45", False) is not None
    assert async_scanner_count(hass, connectable=False) == 1
    assert len(callbacks) == 1

    assert (
        "44:44:33:11:23:45"
        in non_connectable_scanner.discovered_devices_and_advertisement_data
    )

    unavailable_callbacks: list[BluetoothServiceInfoBleak] = []

    @callback
    def _unavailable_callback(service_info: BluetoothServiceInfoBleak) -> None:
        """Wrong device unavailable callback."""
        nonlocal unavailable_callbacks
        unavailable_callbacks.append(service_info.address)

    cancel_unavailable = async_track_unavailable(
        hass,
        _unavailable_callback,
        switchbot_device_non_connectable.address,
        connectable=False,
    )

    assert async_scanner_count(hass, connectable=False) == 1

    non_connectable_scanner.clear_all_devices()
    assert (
        "44:44:33:11:23:45"
        not in non_connectable_scanner.discovered_devices_and_advertisement_data
    )
    monotonic_now = time.monotonic()
    with patch.object(
        hass.config_entries.flow,
        "async_progress_by_init_data_type",
        return_value=[{"flow_id": "mock_flow_id"}],
    ) as mock_async_progress_by_init_data_type, patch.object(
        hass.config_entries.flow, "async_abort"
    ) as mock_async_abort, patch_bluetooth_time(
        monotonic_now + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
    await hass.async_block_till_done()
    assert "44:44:33:11:23:45" in unavailable_callbacks

    assert len(mock_async_progress_by_init_data_type.mock_calls) == 1
    assert mock_async_abort.mock_calls[0][1][0] == "mock_flow_id"

    # Test that if the device comes back online, it can be discovered again
    with patch.object(hass.config_entries.flow, "async_init") as mock_config_flow:
        new_switchbot_device_adv = generate_advertisement_data(
            local_name="wohand",
            service_uuids=["050a021a-0000-1000-8000-00805f9b34fb"],
            service_data={"050a021a-0000-1000-8000-00805f9b34fb": b"\n\xff"},
            manufacturer_data={1: b"\x01"},
            rssi=-60,
        )
        non_connectable_scanner.inject_advertisement(
            switchbot_device_non_connectable, new_switchbot_device_adv
        )
        await hass.async_block_till_done()

    assert (
        "44:44:33:11:23:45"
        in non_connectable_scanner.discovered_devices_and_advertisement_data
    )
    assert len(mock_config_flow.mock_calls) == 1
    assert mock_config_flow.mock_calls[0][1][0] == "switchbot"

    cancel_unavailable()

    cancel()
    unsetup_connectable_scanner()
    cancel_connectable_scanner()


async def test_debug_logging(
    hass: HomeAssistant,
    enable_bluetooth: None,
    register_hci0_scanner: None,
    register_hci1_scanner: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test debug logging."""
    assert await async_setup_component(hass, "logger", {"logger": {}})
    await hass.services.async_call(
        "logger",
        "set_level",
        {"homeassistant.components.bluetooth": "DEBUG"},
        blocking=True,
    )
    await hass.async_block_till_done()

    address = "44:44:33:11:23:41"
    start_time_monotonic = 50.0

    switchbot_device_poor_signal_hci0 = generate_ble_device(
        address, "wohand_poor_signal_hci0"
    )
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
    assert "wohand_poor_signal_hci0" in caplog.text
    caplog.clear()

    await hass.services.async_call(
        "logger",
        "set_level",
        {"homeassistant.components.bluetooth": "WARNING"},
        blocking=True,
    )

    switchbot_device_good_signal_hci0 = generate_ble_device(
        address, "wohand_good_signal_hci0"
    )
    switchbot_adv_good_signal_hci0 = generate_advertisement_data(
        local_name="wohand_good_signal_hci0", service_uuids=[], rssi=-33
    )
    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device_good_signal_hci0,
        switchbot_adv_good_signal_hci0,
        start_time_monotonic,
        "hci0",
    )
    assert "wohand_good_signal_hci0" not in caplog.text


async def test_set_fallback_interval_small(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_bluetooth: None,
    macos_adapter: None,
) -> None:
    """Test we can set the fallback advertisement interval."""
    assert async_get_fallback_availability_interval(hass, "44:44:33:11:23:12") is None

    async_set_fallback_availability_interval(hass, "44:44:33:11:23:12", 2.0)
    assert async_get_fallback_availability_interval(hass, "44:44:33:11:23:12") == 2.0

    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:12", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    switchbot_device_went_unavailable = False

    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device,
        switchbot_adv,
        start_monotonic_time,
        SOURCE_LOCAL,
    )

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    assert async_get_learned_advertising_interval(hass, "44:44:33:11:23:12") is None

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass,
        _switchbot_device_unavailable_callback,
        switchbot_device.address,
        connectable=False,
    )

    monotonic_now = start_monotonic_time + 2
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is True
    switchbot_device_unavailable_cancel()

    # We should forget fallback interval after it expires
    assert async_get_fallback_availability_interval(hass, "44:44:33:11:23:12") is None


async def test_set_fallback_interval_big(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    enable_bluetooth: None,
    macos_adapter: None,
) -> None:
    """Test we can set the fallback advertisement interval."""
    assert async_get_fallback_availability_interval(hass, "44:44:33:11:23:12") is None

    # Force the interval to be really big and check it doesn't expire using the default timeout (900)

    async_set_fallback_availability_interval(hass, "44:44:33:11:23:12", 604800.0)
    assert (
        async_get_fallback_availability_interval(hass, "44:44:33:11:23:12") == 604800.0
    )

    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:12", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    switchbot_device_went_unavailable = False

    inject_advertisement_with_time_and_source(
        hass,
        switchbot_device,
        switchbot_adv,
        start_monotonic_time,
        SOURCE_LOCAL,
    )

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    assert async_get_learned_advertising_interval(hass, "44:44:33:11:23:12") is None

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass,
        _switchbot_device_unavailable_callback,
        switchbot_device.address,
        connectable=False,
    )

    # Check that device hasn't expired after a day

    monotonic_now = start_monotonic_time + 86400
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is False

    # Try again after it has expired

    monotonic_now = start_monotonic_time + 604800
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is True

    switchbot_device_unavailable_cancel()

    # We should forget fallback interval after it expires
    assert async_get_fallback_availability_interval(hass, "44:44:33:11:23:12") is None
