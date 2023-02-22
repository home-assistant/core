"""Tests for the Bluetooth integration ActiveBluetoothDataUpdateCoordinator."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
import logging
from typing import Any
from unittest.mock import MagicMock

from bleak.exc import BleakError

from homeassistant.components.bluetooth import (
    DOMAIN,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_coordinator import (
    _T,
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
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
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        address: str,
        mode: BluetoothScanningMode,
        needs_poll_method: Callable[[BluetoothServiceInfoBleak, float | None], bool],
        poll_method: Callable[
            [BluetoothServiceInfoBleak],
            Coroutine[Any, Any, _T],
        ]
        | None = None,
        poll_debouncer: Debouncer[Coroutine[Any, Any, None]] | None = None,
        connectable: bool = True,
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
            poll_debouncer=poll_debouncer,
            connectable=connectable,
        )

    def _async_handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfo,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.passive_data = {"rssi": service_info.rssi}
        super()._async_handle_bluetooth_event(service_info, change)


async def test_basic_usage(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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


async def test_bleak_error_during_polling(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
    """Test bleak error during polling ActiveBluetoothDataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    poll_count = 0

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, seconds_since_last_poll: float | None
    ) -> bool:
        return True

    async def _poll_method(service_info: BluetoothServiceInfoBleak) -> dict[str, Any]:
        nonlocal poll_count
        poll_count += 1
        if poll_count == 1:
            raise BleakError("fake bleak error")
        return {"fake": "data"}

    coordinator = MyCoordinator(
        hass=hass,
        logger=_LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        needs_poll_method=_needs_poll,
        poll_method=_poll_method,
        poll_debouncer=Debouncer(hass, _LOGGER, cooldown=0, immediate=True),
    )
    assert coordinator.available is False  # no data yet

    mock_listener = MagicMock()
    unregister_listener = coordinator.async_add_listener(mock_listener)

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    assert coordinator.data is None
    assert coordinator.last_poll_successful is False

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO_2.rssi}
    assert coordinator.data == {"fake": "data"}
    assert coordinator.last_poll_successful is True

    cancel()
    unregister_listener()


async def test_generic_exception_during_polling(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
    """Test generic exception during polling ActiveBluetoothDataUpdateCoordinator."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    poll_count = 0

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, seconds_since_last_poll: float | None
    ) -> bool:
        return True

    async def _poll_method(service_info: BluetoothServiceInfoBleak) -> dict[str, Any]:
        nonlocal poll_count
        poll_count += 1
        if poll_count == 1:
            raise ValueError("fake error")
        return {"fake": "data"}

    coordinator = MyCoordinator(
        hass=hass,
        logger=_LOGGER,
        address="aa:bb:cc:dd:ee:ff",
        mode=BluetoothScanningMode.ACTIVE,
        needs_poll_method=_needs_poll,
        poll_method=_poll_method,
        poll_debouncer=Debouncer(hass, _LOGGER, cooldown=0, immediate=True),
    )
    assert coordinator.available is False  # no data yet

    mock_listener = MagicMock()
    unregister_listener = coordinator.async_add_listener(mock_listener)

    cancel = coordinator.async_start()

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    assert coordinator.data is None
    assert coordinator.last_poll_successful is False

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO_2)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO_2.rssi}
    assert coordinator.data == {"fake": "data"}
    assert coordinator.last_poll_successful is True

    cancel()
    unregister_listener()


async def test_polling_debounce(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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


async def test_polling_debounce_with_custom_debouncer(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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
        poll_debouncer=Debouncer(hass, _LOGGER, cooldown=0.1, immediate=True),
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
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> None:
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

    inject_bluetooth_service_info(hass, GENERIC_BLUETOOTH_SERVICE_INFO)
    await hass.async_block_till_done()
    assert coordinator.passive_data == {"rssi": GENERIC_BLUETOOTH_SERVICE_INFO.rssi}
    # Data is different again so poll is done
    assert coordinator.data == {"fake": "data"}

    cancel()
    unregister_listener()
