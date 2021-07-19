"""Config flow for Fjäråskupan integration."""
from __future__ import annotations

import asyncio
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from fjaraskupan import device_filter

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

CONST_WAITTIME = 5.0


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fjäråskupan."""

    VERSION = 1

    def __init__(self):
        """Initialize conflig flow."""
        self._devices: dict[str, str] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        self._async_abort_entries_match()

        event = asyncio.Event()

        def detection(device: BLEDevice, advertisement_data: AdvertisementData):
            if device_filter(device, advertisement_data):
                event.set()

        async with BleakScanner(detection_callback=detection):
            try:
                await asyncio.wait_for(event.wait(), CONST_WAITTIME)
            except asyncio.TimeoutError:
                return self.async_abort(reason="no_devices_found")

        return self.async_create_entry(title="Fjäråskupan", data={})
