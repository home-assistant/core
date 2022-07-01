"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
import logging

from aiolifx.aiolifx import Light

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MESSAGE_RETRIES, MESSAGE_TIMEOUT, UNAVAILABLE_GRACE
from .util import AwaitAioLIFX, lifx_features

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 0.35


class LIFXUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific lifx device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: Light,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        self.device = device
        self.lock = asyncio.Lock()
        self.lifx_mac_address = device.mac_addr
        update_interval = timedelta(seconds=10)
        super().__init__(
            hass,
            _LOGGER,
            name=device.ip_addr,
            update_interval=update_interval,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    @callback
    def async_setup(self) -> None:
        """Set up the device."""
        self.device.timeout = MESSAGE_TIMEOUT
        self.device.retry_count = MESSAGE_RETRIES
        self.device.unregister_timeout = UNAVAILABLE_GRACE

    async def _async_update_data(self) -> None:
        """Fetch all device data from the api."""
        if self.lock.locked():
            response = await AwaitAioLIFX().wait(self.device.get_color)
            if response is None:
                raise UpdateFailed(
                    "Failed to fetch state from device: {self.device.ip_addr}"
                )
            self.lifx_mac_address = response.target_address
            if lifx_features(self.device)["multizone"]:
                await self.update_color_zones()

    async def update_color_zones(self):
        """Get updated color information for each zone."""
        zone = 0
        top = 1
        while zone < top:
            # Each get_color_zones can update 8 zones at once
            resp = await AwaitAioLIFX().wait(
                partial(self.device.get_color_zones, start_index=zone)
            )
            if not resp:
                raise UpdateFailed(
                    "Failed to fetch zones from device: {self.device.ip_addr}"
                )
            zone += 8
            top = resp.count

            # We only await multizone responses so don't ask for just one
            if zone == top - 1:
                zone -= 1
