"""Config flow for Fjäråskupan integration."""
from __future__ import annotations

import asyncio

import async_timeout
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from fjaraskupan import device_filter

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_flow import register_discovery_flow

from .const import DOMAIN

CONST_WAIT_TIME = 5.0


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""

    event = asyncio.Event()

    def detection(device: BLEDevice, advertisement_data: AdvertisementData):
        if device_filter(device, advertisement_data):
            event.set()

    async with BleakScanner(
        detection_callback=detection,
        filters={"DuplicateData": True},
    ):
        try:
            async with async_timeout.timeout(CONST_WAIT_TIME):
                await event.wait()
        except asyncio.TimeoutError:
            return False

    return True


register_discovery_flow(DOMAIN, "Fjäråskupan", _async_has_devices)
