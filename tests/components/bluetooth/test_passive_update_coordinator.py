"""Tests for the Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components.bluetooth import DOMAIN, BluetoothChange
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.setup import async_setup_component

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


async def test_basic_usage(hass, mock_bleak_scanner_start):
    """Test basic usage of the PassiveBluetoothDataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    class MyCoordinator(PassiveBluetoothDataUpdateCoordinator):
        def __init__(self, hass, logger, device_id) -> None:
            super().__init__(hass, logger, device_id)
            self.data: dict[str, Any] = {}

        def _async_handle_bluetooth_event(
            self,
            service_info: BluetoothServiceInfo,
            change: BluetoothChange,
        ) -> None:
            """Handle a Bluetooth event."""
            self.data = {"rssi": service_info.rssi}
            super()._async_handle_bluetooth_event(service_info, change)

    coordinator = MyCoordinator(hass, _LOGGER, "aa:bb:cc:dd:ee:ff")
    assert coordinator.available is False  # no data yet
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    mock_listener = MagicMock()
    unregister_listener = coordinator.async_add_listener(mock_listener)

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        coordinator.async_start()

    assert saved_callback is not None

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert len(mock_listener.mock_calls) == 1
    assert coordinator.data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    assert coordinator.available is True

    unregister_listener()
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert len(mock_listener.mock_calls) == 1
    assert coordinator.data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    assert coordinator.available is True
