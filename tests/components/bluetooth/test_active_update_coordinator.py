"""Tests for the Bluetooth integration ActiveBluetoothDataUpdateCoordinator."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import MagicMock

from homeassistant.components.bluetooth import (
    DOMAIN,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from homeassistant.setup import async_setup_component

from . import inject_bluetooth_service_info

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

GENERIC_BLUETOOTH_SERVICE_INFO_2 = BluetoothServiceInfo(
    name="Generic",
    address="aa:bb:cc:dd:ee:ff",
    rssi=-95,
    manufacturer_data={
        2: b"\x01\x01\x01\x01\x01\x01\x01\x01",
    },
    service_data={},
    service_uuids=[],
    source="local",
)


class MyCoordinator(ActiveBluetoothDataUpdateCoordinator[dict[str, Any]]):
    """An example coordinator that subclasses ActiveBluetoothDataUpdateCoordinator."""

    def __init__(
        self,
        hass,
        logger,
        address,
        mode,
        needs_poll_method,
        poll_method,
    ) -> None:
        """Initialize the coordinator."""
        self.passive_data: dict[str, Any] = {}
        super().__init__(
            hass=hass,
            logger=logger,
            address=address,
            mode=mode,
            needs_poll_method=needs_poll_method,
            poll_method=poll_method,
        )

    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.passive_data = {"rssi": service_info.rssi}
        super()._async_handle_bluetooth_event(service_info, change)


async def test_basic_usage(hass, mock_bleak_scanner_start, mock_bluetooth_adapters):
    """Test basic usage of the ActiveBluetoothDataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, seconds_since_last_poll: float | None
    ) -> bool:
        return True

    async def _poll_method(service_info: BluetoothServiceInfoBleak) -> dict[str, Any]:
        return {"fake": "data"}

    coordinator = MyCoordinator(
        hass=hass,
        logger=_LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        needs_poll_method=_needs_poll,
        poll_method=_poll_method,
    )
    assert coordinator.available is False  # no data yet

    mock_listener = MagicMock()
    unregister_listener = coordinator.async_add_listener(mock_listener)

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    assert coordinator.data == {"fake": "data"}

    cancel()
    unregister_listener()


async def test_polling_debounce(
    hass, mock_bleak_scanner_start, mock_bluetooth_adapters
):
    """Test basic usage of the ActiveBluetoothDataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    poll_count = 0

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, seconds_since_last_poll: float | None
    ) -> bool:
        return True

    async def _poll_method(service_info: BluetoothServiceInfoBleak) -> dict[str, Any]:
        nonlocal poll_count
        poll_count += 1
        await asyncio.sleep(0.0001)
        return {"poll_count": poll_count}

    coordinator = MyCoordinator(
        hass=hass,
        logger=_LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        needs_poll_method=_needs_poll,
        poll_method=_poll_method,
    )
    assert coordinator.available is False  # no data yet

    mock_listener = MagicMock()
    unregister_listener = coordinator.async_add_listener(mock_listener)

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    # We should only get one poll because of the debounce
    assert coordinator.data == {"poll_count": 1}

    cancel()
    unregister_listener()


async def test_polling_rejecting_the_first_time(
    hass, mock_bleak_scanner_start, mock_bluetooth_adapters
):
    """Test need_poll rejects the first time ActiveBluetoothDataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    attempt = 0

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, seconds_since_last_poll: float | None
    ) -> bool:
        nonlocal attempt
        attempt += 1
        return attempt != 1

    async def _poll_method(service_info: BluetoothServiceInfoBleak) -> dict[str, Any]:
        return {"fake": "data"}

    coordinator = MyCoordinator(
        hass=hass,
        logger=_LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        needs_poll_method=_needs_poll,
        poll_method=_poll_method,
    )
    assert coordinator.available is False  # no data yet

    mock_listener = MagicMock()
    unregister_listener = coordinator.async_add_listener(mock_listener)

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    # First poll is rejected, so no data yet
    assert coordinator.data is None

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    # Data is the same so no poll check
    assert coordinator.data is None

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO_2.rssi}
    # Data is different so poll is done
    assert coordinator.data == {"fake": "data"}

    cancel()
    unregister_listener()
