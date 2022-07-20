"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
import logging
import math
from typing import Any, cast

from aiolifx.aiolifx import Light
from aiolifx.connection import LIFXConnection
from aiolifx.msgtypes import StateHevCycle, StateLastHevCycleResult
from awesomeversion import AwesomeVersion

from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    IDENTIFY_WAVEFORM,
    HEV_CYCLE_DURATION,
    HEV_CYCLE_LAST_POWER,
    HEV_CYCLE_LAST_RESULT,
    HEV_CYCLE_REMAINING,
    MESSAGE_RETRIES,
    MESSAGE_TIMEOUT,
    TARGET_ANY,
    UNAVAILABLE_GRACE,
)
from .util import async_execute_lifx, get_real_mac_addr, lifx_features

REQUEST_REFRESH_DELAY = 0.35
RSSI_DBM_FW = AwesomeVersion("2.77")

_LOGGER = logging.getLogger(__name__)


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
        self._rssi: int = 0
        self._hev_cycle: dict[str, Any] = {}

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

    @property
    def label(self) -> str:
        """Return the label of the bulb."""
        return cast(str, self.device.label)

    @property
    def rssi(self) -> int:
        """Return RSSI measurement."""
        return self._rssi

    @property
    def hev_cycle(self) -> dict[str, Any]:
        """Return the HEV cycle dictionary."""
        return self._hev_cycle

    def get_rssi_unit_of_measurement(self) -> str:
        """Return the unit of measurement for the RSSI sensor."""
        if AwesomeVersion(self.device.host_firmware_version) > RSSI_DBM_FW:
            return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        return SIGNAL_STRENGTH_DECIBELS

    async def async_identify_bulb(self) -> None:
        """Identify the device by flashing it three times."""
        bulb: Light = self.device
        if bulb.power_level:
            # just flash the bulb for three seconds
            await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
            return
        # Turn the bulb on first, flash for 3 seconds, then turn off
        await self.async_set_power(state=True, duration=1)
        await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
        await asyncio.sleep(3)
        await self.async_set_power(state=False, duration=1)

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

            await self.async_update_wifi_info()

            if lifx_features(self.device)["multizone"]:
                try:
                    await self.async_update_color_zones()
                except asyncio.TimeoutError as ex:
                    raise UpdateFailed(
                        f"Failed to fetch zones from device: {self.device.ip_addr}"
                    ) from ex

            if lifx_features(self.device)["hev"]:
                await self.async_update_hev_cycle()

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

    async def async_set_waveform_optional(
        self, value: dict[str, Any], rapid: bool = False
    ) -> None:
        """Send a set_waveform_optional message to the device."""
        await async_execute_lifx(
            partial(self.device.set_waveform_optional, value=value, rapid=rapid)
        )

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

    async def async_update_wifi_info(self) -> None:
        """Get the bulb's wifi signal strength."""
        _LOGGER.debug("Updating wifi signal strength for %s", self.device.label)
        try:
            wifi_info = await async_execute_lifx(self.device.get_wifiinfo)
            self._rssi = int(math.floor(10 * math.log10(wifi_info.signal) + 0.5))
        except asyncio.TimeoutError as ex:
            raise UpdateFailed(
                f"Failed to fetch RSSI sensor data from device: {self.device.ip_addr}"
            ) from ex

    async def async_update_hev_cycle(self) -> None:
        """Get the current and last HEV cycle data from the bulb."""
        _LOGGER.debug("Updating HEV cycle sensor values for %s", self.device.label)
        try:
            hev_cycle: StateHevCycle = await async_execute_lifx(
                self.device.get_hev_cycle
            )
            self._hev_cycle = {
                HEV_CYCLE_DURATION: hev_cycle.duration,
                HEV_CYCLE_REMAINING: hev_cycle.remaining,
                HEV_CYCLE_LAST_POWER: hev_cycle.last_power,
            }

            last_result: StateLastHevCycleResult = await async_execute_lifx(
                self.device.get_last_hev_cycle_result
            )
            self._hev_cycle[HEV_CYCLE_LAST_RESULT] = (
                str(last_result.result_str)
                .title()
                .replace("_", " ")
                .replace("Homekit", "HomeKit")
                .replace("Lan", "LAN")
            )
            _LOGGER.debug(self._hev_cycle)
        except asyncio.TimeoutError as ex:
            raise UpdateFailed(
                f"Failed to fetch HEV cycle data from device: {self.device.ip_addr}"
            ) from ex
