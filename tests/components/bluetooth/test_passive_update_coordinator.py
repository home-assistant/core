"""Tests for the Bluetooth integration PassiveBluetoothDataUpdateCoordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components.bluetooth import (
    DOMAIN,
    BluetoothChange,
    BluetoothScanningMode,
)
from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import patch_all_discovered_devices, patch_history

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


GENERIC_BLUETOOTH_SERVICE_INFO = BluetoothServiceInfo(
    name="Generic",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-95,
    manufacturer_data={
        1: b"\x01\x01\x01\x01\x01\x01\x01\x01",
    },
    service_data={},
    service_uuids=[],
    source="local",
)


class MyCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """An example coordinator that subclasses PassiveBluetoothDataUpdateCoordinator."""

    def __init__(self, hass, logger, device_id, mode) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, logger, device_id, mode)
        self.data: dict[str, Any] = {}

    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.data = {"rssi": service_info.rssi}
        super()._async_handle_bluetooth_event(service_info, change)


async def test_basic_usage(hass, mock_bleak_scanner_start):
    """Test basic usage of the PassiveBluetoothDataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    coordinator = MyCoordinator(
        hass, _LOGGER, "aa:bb:cc:dd:ee:ff", BluetoothScanningMode.ACTIVE
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    mock_listener = MagicMock()
    unregister_listener = coordinator.async_add_listener(mock_listener)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel = coordinator.async_start()

    assert saved_callback is not None

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    assert len(mock_listener.mock_calls) == 1
    assert coordinator.data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    assert coordinator.available is True

    unregister_listener()
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    assert len(mock_listener.mock_calls) == 1
    assert coordinator.data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    assert coordinator.available is True
    cancel()


async def test_context_compatiblity_with_data_update_coordinator(
    hass, mock_bleak_scanner_start
):
    """Test contexts can be passed for compatibility with DataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    coordinator = MyCoordinator(
        hass, _LOGGER, "aa:bb:cc:dd:ee:ff", BluetoothScanningMode.ACTIVE
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    mock_listener = MagicMock()
    coordinator.async_add_listener(mock_listener)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_start()

    assert not set(coordinator.async_contexts())

    def update_callback1():
        pass

    def update_callback2():
        pass

    unsub1 = coordinator.async_add_listener(update_callback1, 1)
    assert set(coordinator.async_contexts()) == {1}

    unsub2 = coordinator.async_add_listener(update_callback2, 2)
    assert set(coordinator.async_contexts()) == {1, 2}

    unsub1()
    assert set(coordinator.async_contexts()) == {2}

    unsub2()
    assert not set(coordinator.async_contexts())


async def test_unavailable_callbacks_mark_the_coordinator_unavailable(
    hass, mock_bleak_scanner_start
):
    """Test that the coordinator goes unavailable when the bluetooth stack no longer sees the device."""
    with patch(
        "bleak.BleakScanner.discovered_devices",  # Must patch before we setup
        [MagicMock(address="44:44:33:11:23:45")],
    ):
        await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()
    coordinator = MyCoordinator(
        hass, _LOGGER, "aa:bb:cc:dd:ee:ff", BluetoothScanningMode.PASSIVE
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    mock_listener = MagicMock()
    coordinator.async_add_listener(mock_listener)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_start()

    assert coordinator.available is False
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert coordinator.available is True

    with patch_all_discovered_devices(
        [MagicMock(address="44:44:33:11:23:45")]
    ), patch_history({"aa:bb:cc:dd:ee:ff": MagicMock()}):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()
    assert coordinator.available is False

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert coordinator.available is True

    with patch_all_discovered_devices(
        [MagicMock(address="44:44:33:11:23:45")]
    ), patch_history({"aa:bb:cc:dd:ee:ff": MagicMock()}):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()
    assert coordinator.available is False


async def test_passive_bluetooth_coordinator_entity(hass, mock_bleak_scanner_start):
    """Test integration of PassiveBluetoothDataUpdateCoordinator with PassiveBluetoothCoordinatorEntity."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    coordinator = MyCoordinator(
        hass, _LOGGER, "aa:bb:cc:dd:ee:ff", BluetoothScanningMode.ACTIVE
    )
    entity = PassiveBluetoothCoordinatorEntity(coordinator)
    assert entity.available is False

    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_start()

    assert coordinator.available is False
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    assert coordinator.available is True
    entity.hass = hass
    await entity.async_update()
    assert entity.available is True
