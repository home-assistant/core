"""Coordinator object for the Rachio integration."""

from datetime import datetime, timedelta
import logging
from operator import itemgetter
from typing import Any

from rachiopy import Rachio
from requests.exceptions import Timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    KEY_DAY_VIEWS,
    KEY_ID,
    KEY_PROGRAM_RUN_SUMMARIES,
    KEY_START_TIME,
    KEY_VALVES,
)

_LOGGER = logging.getLogger(__name__)

DAY = "day"
MONTH = "month"
YEAR = "year"

UPDATE_DELAY_TIME = 8


class RachioUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator Class for Rachio Hose Timers."""

    def __init__(
        self,
        hass: HomeAssistant,
        rachio: Rachio,
        base_station,
        base_count: int,
    ) -> None:
        """Initialize the Rachio Update Coordinator."""
        self.hass = hass
        self.rachio = rachio
        self.base_station = base_station
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} update coordinator",
            # To avoid exceeding the rate limit, increase polling interval for
            # each additional base station on the account
            update_interval=timedelta(minutes=(base_count + 1)),
            # Debouncer used because the API takes a bit to update state changes
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=UPDATE_DELAY_TIME, immediate=False
            ),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Update smart hose timer data."""
        try:
            data = await self.hass.async_add_executor_job(
                self.rachio.valve.list_valves, self.base_station[KEY_ID]
            )
        except Timeout as err:
            raise UpdateFailed(f"Could not connect to the Rachio API: {err}") from err
        return {valve[KEY_ID]: valve for valve in data[1][KEY_VALVES]}


class RachioScheduleUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Coordinator for fetching hose timer schedules."""

    def __init__(
        self,
        hass: HomeAssistant,
        rachio: Rachio,
        base_station,
    ) -> None:
        """Initialize a Rachio schedule coordinator."""
        self.hass = hass
        self.rachio = rachio
        self.base_station = base_station
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} schedule update coordinator",
            update_interval=timedelta(minutes=30),
        )

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Retrieve data for the past week and the next 60 days."""
        _now: datetime = dt_util.now()
        _time_start = _now - timedelta(days=7)
        _time_end = _now + timedelta(days=60)
        start: dict[str, int] = {
            YEAR: _time_start.year,
            MONTH: _time_start.month,
            DAY: _time_start.day,
        }
        end: dict[str, int] = {
            YEAR: _time_end.year,
            MONTH: _time_end.month,
            DAY: _time_end.day,
        }

        try:
            schedule = await self.hass.async_add_executor_job(
                self.rachio.summary.get_valve_day_views,
                self.base_station[KEY_ID],
                start,
                end,
            )
        except Timeout as err:
            raise UpdateFailed(f"Could not connect to the Rachio API: {err}") from err
        events = []
        # Flatten and sort dates
        for event in schedule[1][KEY_DAY_VIEWS]:
            events.extend(event[KEY_PROGRAM_RUN_SUMMARIES])
        return sorted(events, key=itemgetter(KEY_START_TIME))
