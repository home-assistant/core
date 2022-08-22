"""Coordinator for lifx."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from functools import partial
import logging
from typing import Any, cast

from aiolifx.aiolifx import Light
from aiolifx.connection import LIFXConnection
from awesomeversion import AwesomeVersion

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.typing import StateType
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
    """Base DataUpdateCoordinator for a specific LIFX device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        connection: LIFXConnection,
        update_interval: timedelta,
        debouncer: Debouncer | None,
    ) -> None:
        """Initialise LIFX DataUpdateCoordinator."""
        assert connection.device is not None
        self.connection = connection
        self.device: Light = connection.device
        self.lock = asyncio.Lock()

        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title} ({self.device.ip_addr})",
            update_interval=update_interval,
            request_refresh_debouncer=debouncer,
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


class LIFXLightUpdateCoordinator(LIFXUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific lifx device."""

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
            timedelta(seconds=10),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            Debouncer(hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False),
        )

    async def _async_update_data(self) -> None:
        """Fetch all light data from the bulbs."""

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
        if self.device.power_level:
            # just flash the bulb for three seconds
            await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
            return
        # Turn the bulb on first, flash for 3 seconds, then turn off
        await self.async_set_power(state=True, duration=1)
        await self.async_set_waveform_optional(value=IDENTIFY_WAVEFORM)
        await asyncio.sleep(3)
        await self.async_set_power(state=False, duration=1)


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

    def async_enable_sensor(self, sensor_name: str) -> Callable[[], None]:
        """Enable updates for sensor."""
        setattr(self, f"update_{sensor_name}", True)
        _LOGGER.debug(
            "Enabled %s updates for %s (%s)",
            sensor_name,
            self.device.label,
            self.device.ip_addr,
        )

        @callback
        def disable_sensor() -> None:
            """Disable updates for sensor."""
            setattr(self, f"update_{sensor_name}", False)
            _LOGGER.debug(
                "Disabled %s updates for %s (%s)",
                sensor_name,
                self.device.label,
                self.device.ip_addr,
            )

        return disable_sensor

    def async_get_native_value(self, sensor_name: str) -> StateType:
        """Return the current native value for sensor."""
        return getattr(self, sensor_name, None)

    def get_rssi_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement for the RSSI sensor."""
        if AwesomeVersion(self.device.host_firmware_version) > RSSI_DBM_FW:
            return SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        return SIGNAL_STRENGTH_DECIBELS

    async def _async_update_data(self) -> None:
        """Update sensor data for enabled sensors."""

        async def _async_update_uptime() -> None:
            """Fetch the current uptime value."""
            uptime = get_uptime_from_hostinfo(
                await async_execute_lifx(self.device.get_hostinfo)
            )
            if uptime is not None:
                self.uptime = uptime

        async def _async_update_rssi() -> None:
            """Fetch the current RSSI value."""
            rssi = get_rssi_from_wifiinfo(
                await async_execute_lifx(self.device.get_wifiinfo)
            )
            if rssi is not None:
                self.rssi = rssi

        async def _async_update_hev_cycle_status() -> None:
            """Fetch current HEV cycle status."""
            status = hev_cycle_status(
                await async_execute_lifx(self.device.get_hev_cycle)
            )
            if status is not None:
                (
                    self.hev_cycle_duration,
                    self.hev_cycle_remaining,
                    self.hev_cycle_last_power,
                ) = status

        async def _async_update_last_hev_cycle_result() -> None:
            """Fetch the last HEV cycle result."""
            last_result = last_hev_cycle_result_str(
                await async_execute_lifx(self.device.get_last_hev_cycle_result)
            )
            if last_result is not None:
                self.last_hev_cycle_result = last_result

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
