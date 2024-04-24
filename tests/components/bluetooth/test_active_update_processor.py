"""Tests for the Bluetooth integration PassiveBluetoothDataUpdateCoordinator."""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock, call

from bleak import BleakError
import pytest

from homeassistant.components.bluetooth import (
    DOMAIN,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_processor import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers.debounce import Debouncer
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
    manufacturer_data={1: b"\x01\x01\x01\x01\x01\x01\x01\x01", 2: b"\x02"},
    service_data={},
    service_uuids=[],
    source="local",
)


async def test_basic_usage(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()

    assert coordinator.available is True

    # async_handle_update should have been called twice
    # The first time, it was passed the data from parsing the advertisement
    # The second time, it was passed the data from polling
    assert len(async_handle_update.mock_calls) == 2
    assert async_handle_update.mock_calls[0] == call({"testdata": 0}, False)
    assert async_handle_update.mock_calls[1] == call({"testdata": 1})

    cancel()


async def test_poll_can_be_skipped(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": True})

    flag = False

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": None}, True)

    flag = True

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": True})

    cancel()


async def test_bleak_error_and_recover(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
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

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    cancel = coordinator.async_start()

    # First poll fails
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": None}, False)

    assert (
        "aa:bb:cc:dd:ee:ff: Bluetooth error whilst polling: Connection was aborted"
        in caplog.text
    )

    # Second poll works
    flag = False
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": False})

    cancel()


async def test_poll_failure_and_recover(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    cancel = coordinator.async_start()

    # First poll fails
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": None}, False)

    # Second poll works
    flag = False
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": False})

    cancel()


async def test_second_poll_needed(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    cancel = coordinator.async_start()

    # First poll gets queued
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    # Second poll gets stuck behind first poll
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)

    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": 1})

    cancel()


async def test_rate_limit(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    cancel = coordinator.async_start()

    # First poll gets queued
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    # Second poll gets stuck behind first poll
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    # Third poll gets stuck behind first poll doesn't get queued
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)

    await hass.async_block_till_done()
    assert async_handle_update.mock_calls[-1] == call({"testdata": 1})

    cancel()


async def test_no_polling_after_stop_event(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
    """Test we do not poll after the stop event."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    needs_poll_calls = 0

    def _update_method(service_info: BluetoothServiceInfoBleak):
        return {"testdata": 0}

    def _poll_needed(*args, **kwargs):
        nonlocal needs_poll_calls
        needs_poll_calls += 1
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

    processor = MagicMock()
    coordinator.async_register_processor(processor)
    async_handle_update = processor.async_handle_update

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert needs_poll_calls == 1

    assert coordinator.available is True

    # async_handle_update should have been called twice
    # The first time, it was passed the data from parsing the advertisement
    # The second time, it was passed the data from polling
    assert len(async_handle_update.mock_calls) == 2
    assert async_handle_update.mock_calls[0] == call({"testdata": 0}, False)
    assert async_handle_update.mock_calls[1] == call({"testdata": 1})

    hass.state = CoreState.stopping
    await hass.async_block_till_done()
    assert needs_poll_calls == 1

    # Should not generate a poll now that CoreState is stopping
    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert needs_poll_calls == 1

    cancel()
