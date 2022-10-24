"""Tests for the Bluetooth integration manager."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.scanner import BLEDevice
from bluetooth_adapters import AdvertisementHistory

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.manager import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.setup import async_setup_component

from . import (
    generate_advertisement_data,
    inject_advertisement_with_source,
    inject_advertisement_with_time_and_source,
    inject_advertisement_with_time_and_source_connectable,
)


async def test_advertisements_do_not_switch_adapters_for_no_reason(
    hass, enable_bluetooth
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


async def test_switching_adapters_based_on_rssi(hass, enable_bluetooth):
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


async def test_switching_adapters_based_on_zero_rssi(hass, enable_bluetooth):
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


async def test_switching_adapters_based_on_stale(hass, enable_bluetooth):
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
        "bluetooth_adapters.BlueZDBusObjects",
        return_value=MagicMock(load=AsyncMock(), history=history),
    ):
        assert await async_setup_component(hass, bluetooth.DOMAIN, {})
        await hass.async_block_till_done()

    assert bluetooth.async_ble_device_from_address(hass, address) is ble_device


async def test_switching_adapters_based_on_rssi_connectable_to_non_connectable(
    hass, enable_bluetooth
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
    hass, enable_bluetooth
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
