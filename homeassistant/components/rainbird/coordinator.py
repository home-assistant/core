"""Update coordinators for rainbird."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
from functools import cached_property
import logging

import aiohttp
from pyrainbird.async_client import (
    AsyncRainbirdController,
    RainbirdApiException,
    RainbirdDeviceBusyException,
)
from pyrainbird.data import ModelAndVersion, Schedule

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER, TIMEOUT_SECONDS

UPDATE_INTERVAL = datetime.timedelta(minutes=1)
# The calendar data requires RPCs for each program/zone, and the data rarely
# changes, so we refresh it less often.
CALENDAR_UPDATE_INTERVAL = datetime.timedelta(minutes=15)

# The valves state are not immediately reflected after issuing a command. We add
# small delay to give additional time to reflect the new state.
DEBOUNCER_COOLDOWN = 5

# Rainbird devices can only accept a single request at a time
CONECTION_LIMIT = 1

_LOGGER = logging.getLogger(__name__)


@dataclass
class RainbirdDeviceState:
    """Data retrieved from a Rain Bird device."""

    zones: set[int]
    active_zones: set[int]
    rain: bool
    rain_delay: int


def async_create_clientsession() -> aiohttp.ClientSession:
    """Create a rainbird async_create_clientsession with a connection limit."""
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(limit=CONECTION_LIMIT),
    )


class RainbirdUpdateCoordinator(DataUpdateCoordinator[RainbirdDeviceState]):
    """Coordinator for rainbird API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        controller: AsyncRainbirdController,
        unique_id: str | None,
        model_info: ModelAndVersion,
    ) -> None:
        """Initialize RainbirdUpdateCoordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=UPDATE_INTERVAL,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=DEBOUNCER_COOLDOWN, immediate=False
            ),
        )
        self._controller = controller
        self._unique_id = unique_id
        self._zones: set[int] | None = None
        self._model_info = model_info

    @property
    def controller(self) -> AsyncRainbirdController:
        """Return the API client for the device."""
        return self._controller

    @property
    def unique_id(self) -> str | None:
        """Return the config entry unique id."""
        return self._unique_id

    @property
    def device_name(self) -> str:
        """Device name for the rainbird controller."""
        return f"{MANUFACTURER} Controller"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return information about the device."""
        if self._unique_id is None:
            return None
        return DeviceInfo(
            name=self.device_name,
            identifiers={(DOMAIN, self._unique_id)},
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
            async with asyncio.timeout(TIMEOUT_SECONDS):
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
            unique_id=self.entry.unique_id,
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
