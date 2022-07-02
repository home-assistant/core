"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
import logging
from typing import cast

from aiolifx.aiolifx import Light
from aiolifx.connection import AwaitAioLIFX, LIFXConnection

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MESSAGE_RETRIES, MESSAGE_TIMEOUT, TARGET_ANY, UNAVAILABLE_GRACE
from .util import get_real_mac_addr, lifx_features

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 0.35


class LIFXUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific lifx device."""

    def __init__(
        self,
        hass: HomeAssistant,
        connection: LIFXConnection,
        title: str,
    ) -> None:
        """Initialize DataUpdateCoordinator."""
        assert connection.device is not None
        self.connection = connection
        self.device: Light = connection.device
        self.lock = asyncio.Lock()
        update_interval = timedelta(seconds=10)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{title} ({self.device.ip_addr})",
            update_interval=update_interval,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    @callback
    def async_setup(self) -> None:
        """Change timeouts."""
        self.device.timeout = MESSAGE_TIMEOUT
        self.device.retry_count = MESSAGE_RETRIES
        self.device.unregister_timeout = UNAVAILABLE_GRACE

    @property
    def internal_mac_address(self) -> str:
        """Return the internal mac address."""
        return cast(str, self.device.mac_addr)

    @property
    def physical_mac_address(self) -> str:
        """Return the physical mac address."""
        return get_real_mac_addr(
            self.device.mac_addr, self.device.host_firmware_version
        )

    async def _async_update_data(self) -> None:
        """Fetch all device data from the api."""
        async with self.lock:
            if self.device.product is None:
                await AwaitAioLIFX().wait(self.device.get_version)
            if self.device.product is None:
                raise UpdateFailed(
                    f"Failed to fetch get version from device: {self.device.ip_addr}"
                )

            response = await AwaitAioLIFX().wait(self.device.get_color)
            if response is None:
                raise UpdateFailed(
                    f"Failed to fetch state from device: {self.device.ip_addr}"
                )
            if self.device.mac_addr == TARGET_ANY:
                self.device.mac_addr = response.target_addr
            if lifx_features(self.device)["multizone"]:
                await self._update_color_zones()

    async def _update_color_zones(self) -> None:
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
                    f"Failed to fetch zones from device: {self.device.ip_addr}"
                )
            zone += 8
            top = resp.count

            # We only await multizone responses so don't ask for just one
            if zone == top - 1:
                zone -= 1
