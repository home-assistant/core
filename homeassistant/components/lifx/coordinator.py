"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from functools import partial
import logging
from typing import Any, cast

from aiolifx.aiolifx import Light
from aiolifx.connection import LIFXConnection
from awesomeversion import AwesomeVersion

from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    IDENTIFY_WAVEFORM,
    MESSAGE_RETRIES,
    MESSAGE_TIMEOUT,
    TARGET_ANY,
    UNAVAILABLE_GRACE,
)

from .util import (
    async_execute_lifx,
    get_real_mac_addr,
    get_rssi_from_wifiinfo,
    get_uptime_from_hostinfo,
    hev_cycle_status,
    last_hev_cycle_result_str,
    lifx_features,
)

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

        self.fetch_rssi: bool = False
        self.fetch_hev_cycle_duration: bool = False
        self.fetch_hev_cycle_remaining: bool = False
        self.fetch_hev_cycle_last_power: bool = False
        self.fetch_last_hev_cycle_result: bool = False

        self.rssi: int = 0
        self.hev_cycle_duration: int = 7200
        self.hev_cycle_remaining: int = 0
        self.hev_cycle_last_power: bool = False
        self.last_hev_cycle_result: str = STATE_UNKNOWN

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

    def get_rssi_unit_of_measurement(self) -> str | None:
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

        async def _async_update_rssi() -> None:
            """Fetch the current RSSI value if the sensor is enabled."""
            try:
                self.rssi = get_rssi_from_wifiinfo(
                    await async_execute_lifx(self.device.get_wifiinfo)
                )
            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch RSSI value from device: {self.device.label} ({self.device.ip_addr})"
                ) from ex

        async def _async_update_hev_cycle_status() -> None:
            """Fetch current measurement for enabled HEV sensors."""
            try:
                (
                    self.hev_cycle_duration,
                    self.hev_cycle_remaining,
                    self.hev_cycle_last_power,
                ) = hev_cycle_status(
                    await async_execute_lifx(self.device.get_hev_cycle)
                )
            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch HEV cycle status from device: {self.device.label}() {self.device.ip_addr})"
                ) from ex

        async def _async_update_last_hev_cycle_result() -> None:
            """Fetch the last HEV cycle result."""
            try:
                self.last_hev_cycle_result = last_hev_cycle_result_str(
                    await async_execute_lifx(self.device.get_last_hev_cycle_result)
                )
            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch last HEV cycle result from device: {self.device.label}() {self.device.ip_addr})"
                ) from ex

        async with self.lock:
            # Handle sensor updates first
            if lifx_features(self.device)["hev"]:
                if (
                    self.fetch_hev_cycle_duration is True
                    or self.fetch_hev_cycle_remaining is True
                    or self.fetch_hev_cycle_last_power is True
                ):
                    await _async_update_hev_cycle_status()

                if self.fetch_last_hev_cycle_result is True:
                    await _async_update_last_hev_cycle_result()

            if self.fetch_rssi is True:
                await _async_update_rssi()

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
                        f"Failed to fetch zones from device: {self.device.label} ({self.device.ip_addr})"
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

    async def async_identify_bulb(self) -> None:
        """Identify the device by flashing it three times."""
        await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)


class LIFXSensorUpdateCoordinator(LIFXUpdateCoordinator):
    """DataUpdateCoordinator for sensor data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        connection: LIFXConnection,
    ) -> None:
        """Initialize LIFX DataUpdateCoordinator."""
        super().__init__(
            hass,
            entry,
            connection,
            timedelta(seconds=60),
            Debouncer(hass, _LOGGER, cooldown=0, immediate=True),
        )

        self.update_rssi: bool = False
        self.update_uptime: bool = False
        self.update_hev_cycle_duration: bool = False
        self.update_hev_cycle_remaining: bool = False
        self.update_hev_cycle_last_power: bool = False
        self.update_last_hev_cycle_result: bool = False

        self.rssi: int = 0
        self.uptime: int = 0
        self.hev_cycle_duration: int = 7200
        self.hev_cycle_remaining: int = 0
        self.hev_cycle_last_power: bool = False
        self.last_hev_cycle_result: str = STATE_UNKNOWN

    def get_rssi_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for the RSSI sensor."""
        if AwesomeVersion(self.device.host_firmware_version) > RSSI_DBM_FW:
            return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        return SIGNAL_STRENGTH_DECIBELS

    async def _async_update_data(self) -> None:
        async def _async_update_uptime() -> None:
            """Fetch the current uptime value."""
            try:
                uptime = get_uptime_from_hostinfo(
                    await async_execute_lifx(self.device.get_hostinfo)
                )
                if uptime is not None:
                    self.uptime = uptime

            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch uptime: {self.device.label} ({self.device.ip_addr})"
                ) from ex

        async def _async_update_rssi() -> None:
            """Fetch the current RSSI value."""
            try:
                rssi = get_rssi_from_wifiinfo(
                    await async_execute_lifx(self.device.get_wifiinfo)
                )
                if rssi is not None:
                    self.rssi = rssi
            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch RSSI: {self.device.label} ({self.device.ip_addr})"
                ) from ex

        async def _async_update_hev_cycle_status() -> None:
            """Fetch current HEV cycle status."""
            try:
                status = hev_cycle_status(
                    await async_execute_lifx(self.device.get_hev_cycle)
                )
                if status is not None:
                    (
                        self.hev_cycle_duration,
                        self.hev_cycle_remaining,
                        self.hev_cycle_last_power,
                    ) = status

            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch HEV cycle status from device: {self.device.label}() {self.device.ip_addr})"
                ) from ex

        async def _async_update_last_hev_cycle_result() -> None:
            """Fetch the last HEV cycle result."""
            try:
                last_result = last_hev_cycle_result_str(
                    await async_execute_lifx(self.device.get_last_hev_cycle_result)
                )
                if last_result is not None:
                    self.last_hev_cycle_result = last_result

            except asyncio.TimeoutError as ex:
                raise UpdateFailed(
                    f"Failed to fetch last HEV cycle result from device: {self.device.label}() {self.device.ip_addr})"
                ) from ex

        async with self.lock:

            # Only fetch data for enabled sensors
            if self.update_rssi is True:
                await _async_update_rssi()

            if self.update_uptime is True:
                await _async_update_uptime()

            if lifx_features(self.device)["hev"]:
                if (
                    self.update_hev_cycle_duration is True
                    or self.update_hev_cycle_remaining is True
                    or self.update_hev_cycle_last_power is True
                ):
                    await _async_update_hev_cycle_status()

                if self.update_last_hev_cycle_result is True:
                    await _async_update_last_hev_cycle_result()
