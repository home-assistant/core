"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
from typing import cast

from aiolifx.aiolifx import Light
from aiolifx_connection import LIFXConnection

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    MESSAGE_RETRIES,
    MESSAGE_TIMEOUT,
    TARGET_ANY,
    UNAVAILABLE_GRACE,
)
from .util import async_execute_lifx, get_real_mac_addr, lifx_features

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
    def serial_number(self) -> str:
        """Return the internal mac address."""
        return cast(
            str, self.device.mac_addr
        )  # device.mac_addr is not the mac_address, its the serial number

    @property
    def mac_address(self) -> str:
        """Return the physical mac address."""
        return get_real_mac_addr(
            # device.mac_addr is not the mac_address, its the serial number
            self.device.mac_addr,
            self.device.host_firmware_version,
        )

    async def _async_update_data(self) -> None:
        """Fetch all device data from the api."""
        async with self.lock:
            if self.device.host_firmware_version is None:
                self.device.get_hostfirmware()
            if self.device.product is None:
                self.device.get_version()
            try:
                response = await async_execute_lifx(self.device.get_color)
            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch state from device: {self.device.ip_addr}"
                ) from ex
            if self.device.product is None:
                raise UpdateFailed(
                    f"Failed to fetch get version from device: {self.device.ip_addr}"
                )
            # device.mac_addr is not the mac_address, its the serial number
            if self.device.mac_addr == TARGET_ANY:
                self.device.mac_addr = response.target_addr
            if lifx_features(self.device)["multizone"]:
                try:
                    await self.async_update_color_zones()
                except asyncio.TimeoutError as ex:
                    raise UpdateFailed(
                        f"Failed to fetch zones from device: {self.device.ip_addr}"
                    ) from ex

    async def async_update_color_zones(self) -> None:
        """Get updated color information for each zone."""
        zone = 0
        top = 1
        while zone < top:
            # Each get_color_zones can update 8 zones at once
            resp = await async_execute_lifx(
                partial(self.device.get_color_zones, start_index=zone)
            )
            zone += 8
            top = resp.count

            # We only await multizone responses so don't ask for just one
            if zone == top - 1:
                zone -= 1

    async def async_get_color(self) -> None:
        """Send a get color message to the device."""
        await async_execute_lifx(self.device.get_color)

    async def async_set_power(self, state: bool, duration: int | None) -> None:
        """Send a set power message to the device."""
        await async_execute_lifx(
            partial(self.device.set_power, state, duration=duration)
        )

    async def async_set_color(
        self, hsbk: list[float | int | None], duration: int | None
    ) -> None:
        """Send a set color message to the device."""
        await async_execute_lifx(
            partial(self.device.set_color, hsbk, duration=duration)
        )

    async def async_set_color_zones(
        self,
        start_index: int,
        end_index: int,
        hsbk: list[float | int | None],
        duration: int | None,
        apply: int,
    ) -> None:
        """Send a set color zones message to the device."""
        await async_execute_lifx(
            partial(
                self.device.set_color_zones,
                start_index=start_index,
                end_index=end_index,
                color=hsbk,
                duration=duration,
                apply=apply,
            )
        )
