"""Update coordinators for rainbird."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
from functools import cached_property
import logging
from typing import TypeVar

import async_timeout
from pyrainbird.async_client import (
    AsyncRainbirdController,
    RainbirdApiException,
    RainbirdDeviceBusyException,
)
from pyrainbird.data import ModelAndVersion, Schedule

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SERIAL_NUMBER, DOMAIN, MANUFACTURER, TIMEOUT_SECONDS

UPDATE_INTERVAL = datetime.timedelta(minutes=1)
# The calendar data requires RPCs for each program/zone, and the data rarely
# changes, so we refresh it less often. However, the calendar entity state refreshes more
# frequently to check for the start of an event.
CALENDAR_UPDATE_INTERVAL = datetime.timedelta(minutes=15)

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


@dataclass
class RainbirdDeviceState:
    """Data retrieved from a Rain Bird device."""

    zones: set[int]
    active_zones: set[int]
    rain: bool
    rain_delay: int


class RainbirdUpdateCoordinator(DataUpdateCoordinator[RainbirdDeviceState]):
    """Coordinator for rainbird API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        controller: AsyncRainbirdController,
        serial_number: str,
        model_info: ModelAndVersion,
    ) -> None:
        """Initialize RainbirdUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_method=self._async_update_data,
            update_interval=UPDATE_INTERVAL,
        )
        self._controller = controller
        self._serial_number = serial_number
        self._zones: set[int] | None = None
        self._model_info = model_info

    @property
    def controller(self) -> AsyncRainbirdController:
        """Return the API client for the device."""
        return self._controller

    @property
    def serial_number(self) -> str:
        """Return the device serial number."""
        return self._serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            name=f"{MANUFACTURER} Controller",
            identifiers={(DOMAIN, self._serial_number)},
            manufacturer=MANUFACTURER,
            model=self._model_info.model_name,
            sw_version=f"{self._model_info.major}.{self._model_info.minor}",
        )

    async def _async_update_data(self) -> RainbirdDeviceState:
        """Fetch data from Rain Bird device."""
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                return await self._fetch_data()
        except RainbirdDeviceBusyException as err:
            raise UpdateFailed("Rain Bird device is busy") from err
        except RainbirdApiException as err:
            raise UpdateFailed("Rain Bird device failure") from err

    async def _fetch_data(self) -> RainbirdDeviceState:
        """Fetch data from the Rain Bird device.

        Rainbird devices can only reliably handle a single request at a time,
        so the requests are sent serially.
        """
        available_stations = await self._controller.get_available_stations()
        states = await self._controller.get_zone_states()
        rain = await self._controller.get_rain_sensor_state()
        rain_delay = await self._controller.get_rain_delay()
        return RainbirdDeviceState(
            zones=available_stations.active_set,
            active_zones=states.active_set,
            rain=rain,
            rain_delay=rain_delay,
        )


class RainbirdScheduleUpdateCoordinator(DataUpdateCoordinator[Schedule]):
    """Coordinator for rainbird irrigation schedule calls."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        controller: AsyncRainbirdController,
    ) -> None:
        """Initialize ZoneStateUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_method=self._async_update_data,
            update_interval=CALENDAR_UPDATE_INTERVAL,
        )
        self._controller = controller

    async def _async_update_data(self) -> Schedule:
        """Fetch data from Rain Bird device."""
        try:
            async with async_timeout.timeout(TIMEOUT_SECONDS):
                return await self._controller.get_schedule()
        except RainbirdApiException as err:
            raise UpdateFailed(f"Error communicating with Device: {err}") from err


@dataclass
class RainbirdData:
    """Holder for shared integration data.

    The coordinators are lazy since they may only be used by some platforms when needed.
    """

    hass: HomeAssistant
    entry: ConfigEntry
    controller: AsyncRainbirdController
    model_info: ModelAndVersion

    @cached_property
    def coordinator(self) -> RainbirdUpdateCoordinator:
        """Return RainbirdUpdateCoordinator."""
        return RainbirdUpdateCoordinator(
            self.hass,
            name=self.entry.title,
            controller=self.controller,
            serial_number=self.entry.data[CONF_SERIAL_NUMBER],
            model_info=self.model_info,
        )

    @cached_property
    def schedule_coordinator(self) -> RainbirdScheduleUpdateCoordinator:
        """Return RainbirdScheduleUpdateCoordinator."""
        return RainbirdScheduleUpdateCoordinator(
            self.hass,
            name=f"{self.entry.title} Schedule",
            controller=self.controller,
        )
