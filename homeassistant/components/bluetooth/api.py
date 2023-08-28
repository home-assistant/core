"""The bluetooth integration apis.

These APIs are the only documented way to interact with the bluetooth integration.
"""
from __future__ import annotations

import asyncio
from asyncio import Future
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, cast

from home_assistant_bluetooth import BluetoothServiceInfoBleak

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback

from .base_scanner import BaseHaScanner, BluetoothScannerDevice
from .const import DATA_MANAGER
from .manager import BluetoothManager
from .match import BluetoothCallbackMatcher
from .models import (
    BluetoothCallback,
    BluetoothChange,
    BluetoothScanningMode,
    ProcessAdvertisementCallback,
)
from .wrappers import HaBleakScannerWrapper

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice


def _get_manager(hass: HomeAssistant) -> BluetoothManager:
    """Get the bluetooth manager."""
    return cast(BluetoothManager, hass.data[DATA_MANAGER])


@hass_callback
def async_get_scanner(hass: HomeAssistant) -> HaBleakScannerWrapper:
    """Return a HaBleakScannerWrapper.

    This is a wrapper around our BleakScanner singleton that allows
    multiple integrations to share the same BleakScanner.
    """
    return HaBleakScannerWrapper()


@hass_callback
def async_scanner_by_source(hass: HomeAssistant, source: str) -> BaseHaScanner | None:
    """Return a scanner for a given source.

    This method is only intended to be used by integrations that implement
    a bluetooth client and need to interact with a scanner directly.

    It is not intended to be used by integrations that need to interact
    with a device.
    """
    return _get_manager(hass).async_scanner_by_source(source)


@hass_callback
def async_scanner_count(hass: HomeAssistant, connectable: bool = True) -> int:
    """Return the number of scanners currently in use."""
    return _get_manager(hass).async_scanner_count(connectable)


@hass_callback
def async_discovered_service_info(
    hass: HomeAssistant, connectable: bool = True
) -> Iterable[BluetoothServiceInfoBleak]:
    """Return the discovered devices list."""
    if DATA_MANAGER not in hass.data:
        return []
    return _get_manager(hass).async_discovered_service_info(connectable)


@hass_callback
def async_last_service_info(
    hass: HomeAssistant, address: str, connectable: bool = True
) -> BluetoothServiceInfoBleak | None:
    """Return the last service info for an address."""
    if DATA_MANAGER not in hass.data:
        return None
    return _get_manager(hass).async_last_service_info(address, connectable)


@hass_callback
def async_ble_device_from_address(
    hass: HomeAssistant, address: str, connectable: bool = True
) -> BLEDevice | None:
    """Return BLEDevice for an address if its present."""
    if DATA_MANAGER not in hass.data:
        return None
    return _get_manager(hass).async_ble_device_from_address(address, connectable)


@hass_callback
def async_scanner_devices_by_address(
    hass: HomeAssistant, address: str, connectable: bool = True
) -> list[BluetoothScannerDevice]:
    """Return all discovered BluetoothScannerDevice for an address."""
    return _get_manager(hass).async_scanner_devices_by_address(address, connectable)


@hass_callback
def async_address_present(
    hass: HomeAssistant, address: str, connectable: bool = True
) -> bool:
    """Check if an address is present in the bluetooth device list."""
    if DATA_MANAGER not in hass.data:
        return False
    return _get_manager(hass).async_address_present(address, connectable)


@hass_callback
def async_register_callback(
    hass: HomeAssistant,
    callback: BluetoothCallback,
    match_dict: BluetoothCallbackMatcher | None,
    mode: BluetoothScanningMode,
) -> Callable[[], None]:
    """Register to receive a callback on bluetooth change.

    mode is currently not used as we only support active scanning.
    Passive scanning will be available in the future. The flag
    is required to be present to avoid a future breaking change
    when we support passive scanning.

    Returns a callback that can be used to cancel the registration.
    """
    return _get_manager(hass).async_register_callback(callback, match_dict)


async def async_process_advertisements(
    hass: HomeAssistant,
    callback: ProcessAdvertisementCallback,
    match_dict: BluetoothCallbackMatcher,
    mode: BluetoothScanningMode,
    timeout: int,
) -> BluetoothServiceInfoBleak:
    """Process advertisements until callback returns true or timeout expires."""
    done: Future[BluetoothServiceInfoBleak] = Future()

    @hass_callback
    def _async_discovered_device(
        service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        if not done.done() and callback(service_info):
            done.set_result(service_info)

    unload = _get_manager(hass).async_register_callback(
        _async_discovered_device, match_dict
    )

    try:
        async with asyncio.timeout(timeout):
            return await done
    finally:
        unload()


@hass_callback
def async_track_unavailable(
    hass: HomeAssistant,
    callback: Callable[[BluetoothServiceInfoBleak], None],
    address: str,
    connectable: bool = True,
) -> Callable[[], None]:
    """Register to receive a callback when an address is unavailable.

    Returns a callback that can be used to cancel the registration.
    """
    return _get_manager(hass).async_track_unavailable(callback, address, connectable)


@hass_callback
def async_rediscover_address(hass: HomeAssistant, address: str) -> None:
    """Trigger discovery of devices which have already been seen."""
    _get_manager(hass).async_rediscover_address(address)


@hass_callback
def async_register_scanner(
    hass: HomeAssistant,
    scanner: BaseHaScanner,
    connectable: bool,
    connection_slots: int | None = None,
) -> CALLBACK_TYPE:
    """Register a BleakScanner."""
    return _get_manager(hass).async_register_scanner(
        scanner, connectable, connection_slots
    )


@hass_callback
def async_get_advertisement_callback(
    hass: HomeAssistant,
) -> Callable[[BluetoothServiceInfoBleak], None]:
    """Get the advertisement callback."""
    return _get_manager(hass).scanner_adv_received
