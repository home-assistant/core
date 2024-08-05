"""Bluetooth support for esphome."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from aioesphomeapi import APIClient, DeviceInfo
from bleak_esphome import connect_scanner
from bleak_esphome.backend.cache import ESPHomeBluetoothCache

from homeassistant.components.bluetooth import async_register_scanner
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback

from .entry_data import RuntimeEntryData


@hass_callback
def _async_unload(unload_callbacks: list[CALLBACK_TYPE]) -> None:
    """Cancel all the callbacks on unload."""
    for callback in unload_callbacks:
        callback()


@hass_callback
def async_connect_scanner(
    hass: HomeAssistant,
    entry_data: RuntimeEntryData,
    cli: APIClient,
    device_info: DeviceInfo,
    cache: ESPHomeBluetoothCache,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    client_data = connect_scanner(cli, device_info, cache, entry_data.available)
    entry_data.bluetooth_device = client_data.bluetooth_device
    client_data.disconnect_callbacks = entry_data.disconnect_callbacks
    scanner = client_data.scanner
    if TYPE_CHECKING:
        assert scanner is not None
    return partial(
        _async_unload,
        [
            async_register_scanner(hass, scanner),
            scanner.async_setup(),
        ],
    )
