"""Tests for the Bluetooth integration PassiveBluetoothDataUpdateCoordinator."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock, call, patch

from bleak import BleakError

from homeassistant.components.bluetooth import (
    DOMAIN,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
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


async def test_basic_usage(hass: HomeAssistant, mock_bleak_scanner_start):
    """Test basic usage of the ActiveBluetoothProcessorCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    def _update_method(service_info: BluetoothServiceInfoBleak):
        return {"testdata": 0}

    def _poll_needed(*args, **kwargs):
        return True

    async def _poll(*args, **kwargs):
        return {"testdata": 1}

    coordinator = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_update_method,
        needs_poll_method=_poll_needed,
        poll_method=_poll,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel = coordinator.async_start()

    assert saved_callback is not None

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()

    assert coordinator.available is True

    # async_handle_update should have been called twice
    # The first time, it was passed the data from parsing the advertisement
    # The second time, it was passed the data from polling
    assert len(async_handle_update.mock_calls) == 2
    assert async_handle_update.mock_calls[0] == call({"testdata": 0})
    assert async_handle_update.mock_calls[1] == call({"testdata": 1})

    cancel()


async def test_poll_can_be_skipped(hass: HomeAssistant, mock_bleak_scanner_start):
    """Test need_poll callback works and can skip a poll if its not needed."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    flag = True

    def _update_method(service_info: BluetoothServiceInfoBleak):
        return {"testdata": None}

    def _poll_needed(*args, **kwargs):
        nonlocal flag
        return flag

    async def _poll(*args, **kwargs):
        return {"testdata": flag}

    coordinator = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_update_method,
        needs_poll_method=_poll_needed,
        poll_method=_poll,
        poll_debouncer=Debouncer(
            hass,
            _LOGGER,
            cooldown=0,
            immediate=True,
        ),
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel = coordinator.async_start()

    assert saved_callback is not None

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": True})

    flag = False

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": None})

    flag = True

    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": True})

    cancel()


async def test_bleak_error_and_recover(
    hass: HomeAssistant, mock_bleak_scanner_start, caplog
):
    """Test bleak error handling and recovery."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    flag = True

    def _update_method(service_info: BluetoothServiceInfoBleak):
        return {"testdata": None}

    def _poll_needed(*args, **kwargs):
        return True

    async def _poll(*args, **kwargs):
        nonlocal flag
        if flag:
            raise BleakError("Connection was aborted")
        return {"testdata": flag}

    coordinator = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_update_method,
        needs_poll_method=_poll_needed,
        poll_method=_poll,
        poll_debouncer=Debouncer(
            hass,
            _LOGGER,
            cooldown=0,
            immediate=True,
        ),
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel = coordinator.async_start()

    assert saved_callback is not None

    # First poll fails
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": None})

    assert (
        "aa:bb:cc:dd:ee:ff: Bluetooth error whilst polling: Connection was aborted"
        in caplog.text
    )

    # Second poll works
    flag = False
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": False})

    cancel()


async def test_poll_failure_and_recover(hass: HomeAssistant, mock_bleak_scanner_start):
    """Test error handling and recovery."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    flag = True

    def _update_method(service_info: BluetoothServiceInfoBleak):
        return {"testdata": None}

    def _poll_needed(*args, **kwargs):
        return True

    async def _poll(*args, **kwargs):
        nonlocal flag
        if flag:
            raise RuntimeError("Poll failure")
        return {"testdata": flag}

    coordinator = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_update_method,
        needs_poll_method=_poll_needed,
        poll_method=_poll,
        poll_debouncer=Debouncer(
            hass,
            _LOGGER,
            cooldown=0,
            immediate=True,
        ),
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel = coordinator.async_start()

    assert saved_callback is not None

    # First poll fails
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": None})

    # Second poll works
    flag = False
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": False})

    cancel()


async def test_second_poll_needed(hass: HomeAssistant, mock_bleak_scanner_start):
    """If a poll is queued, by the time it starts it may no longer be needed."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    count = 0

    def _update_method(service_info: BluetoothServiceInfoBleak):
        return {"testdata": None}

    # Only poll once
    def _poll_needed(*args, **kwargs):
        nonlocal count
        return count == 0

    async def _poll(*args, **kwargs):
        nonlocal count
        count += 1
        return {"testdata": count}

    coordinator = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_update_method,
        needs_poll_method=_poll_needed,
        poll_method=_poll,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel = coordinator.async_start()

    assert saved_callback is not None

    # First poll gets queued
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # Second poll gets stuck behind first poll
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": 1})

    cancel()


async def test_rate_limit(hass: HomeAssistant, mock_bleak_scanner_start):
    """Test error handling and recovery."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    count = 0

    def _update_method(service_info: BluetoothServiceInfoBleak):
        return {"testdata": None}

    def _poll_needed(*args, **kwargs):
        return True

    async def _poll(*args, **kwargs):
        nonlocal count
        count += 1
        await asyncio.sleep(0)
        return {"testdata": count}

    coordinator = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        update_method=_update_method,
        needs_poll_method=_poll_needed,
        poll_method=_poll,
    )
    assert coordinator.available is False  # no data yet
    saved_callback = None

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        cancel = coordinator.async_start()

    assert saved_callback is not None

    # First poll gets queued
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # Second poll gets stuck behind first poll
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)
    # Third poll gets stuck behind first poll doesn't get queued
    saved_callback(GENERIC_BLUETOOTH_SERVICE_INFO, BluetoothChange.ADVERTISEMENT)

    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": 1})

    cancel()
