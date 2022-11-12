"""Bluetooth support for shelly."""
from __future__ import annotations

import logging

from aioshelly.block_device import BlockDevice

from homeassistant.components.bluetooth import (
    async_get_advertisement_callback,
    async_register_scanner,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback as hass_callback

from .scanner import ShellyBLEScanner

_LOGGER = logging.getLogger(__name__)


async def async_connect_scanner(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: BlockDevice,
) -> CALLBACK_TYPE:
    """Connect scanner."""
    assert entry.unique_id is not None
    source = str(entry.unique_id)
    new_info_callback = async_get_advertisement_callback(hass)
    scanner = ShellyBLEScanner(hass, source, new_info_callback)
    unload_callbacks = [
        async_register_scanner(hass, scanner, False),
        scanner.async_setup(),
    ]

    @hass_callback
    def _async_unload() -> None:
        for callback in unload_callbacks:
            callback()

    return _async_unload
