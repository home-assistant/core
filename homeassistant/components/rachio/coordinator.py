"""Coordinator object for the Rachio integration."""

from datetime import datetime, timedelta
from http import HTTPStatus
import logging
from operator import itemgetter
from typing import TYPE_CHECKING, Any, override

from rachiopy import Rachio
from requests.exceptions import RequestException, Timeout

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    KEY_DAY_VIEWS,
    KEY_ID,
    KEY_PROGRAM_RUN_SUMMARIES,
    KEY_START_TIME,
    KEY_STATUS,
    KEY_VALVES,
)

if TYPE_CHECKING:
    from .device import RachioConfigEntry

_LOGGER = logging.getLogger(__name__)

DAY = "day"
MONTH = "month"
YEAR = "year"

UPDATE_DELAY_TIME = 8

HEADER_RATE_REMAINING = "x-ratelimit-remaining"
HEADER_RATE_RESET = "x-ratelimit-reset"
MINUTES_PER_DAY = 24 * 60
# The smart hose timer schedule coordinator polls every 30 minutes
HOSE_TIMER_SCHEDULE_CALLS_PER_DAY = MINUTES_PER_DAY // 30
POLL_INTERVAL_STEP = 0.5
MAX_POLL_INTERVAL = 60
POLL_API_BUDGET_FRACTION = 0.9
# Polling pauses below this many remaining calls so commands keep working
POLL_RESERVE_CALLS = 50


class RachioUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator Class for Rachio Hose Timers."""

    def __init__(
        self,
        hass: HomeAssistant,
        rachio: Rachio,
        config_entry: RachioConfigEntry,
        base_station,
        base_count: int,
    ) -> None:
        """Initialize the Rachio Update Coordinator."""
        self.rachio = rachio
        self.base_station = base_station
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} update coordinator",
            # To avoid exceeding the rate limit, increase polling interval for
            # each additional base station on the account
            update_interval=timedelta(minutes=(base_count + 1)),
            # Debouncer used because the API takes a bit to update state changes
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=UPDATE_DELAY_TIME, immediate=False
            ),
        )

    @override
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
        config_entry: RachioConfigEntry,
        base_station,
    ) -> None:
        """Initialize a Rachio schedule coordinator."""
        self.rachio = rachio
        self.base_station = base_station
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} schedule update coordinator",
            update_interval=timedelta(minutes=30),
        )

    @override
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


def controller_calls_per_day(controller_count: int, interval_minutes: float) -> int:
    """Return the API calls per day used by polling controllers."""
    return round(controller_count * MINUTES_PER_DAY / interval_minutes)


def hose_timer_calls_per_day(base_count: int) -> int:
    """Return the API calls per day used by the smart hose timer coordinators."""
    if not base_count:
        return 0
    # Each status coordinator polls every (base_count + 1) minutes.
    status_calls = round(base_count * MINUTES_PER_DAY / (base_count + 1))
    return status_calls + base_count * HOSE_TIMER_SCHEDULE_CALLS_PER_DAY


def min_poll_interval(
    controller_count: int, base_count: int, call_limit: int
) -> float | None:
    """Return the shortest interval, in minutes, that stays within the API budget.

    Returns None if even the longest interval would use more than the budget.
    """
    budget = call_limit * POLL_API_BUDGET_FRACTION - hose_timer_calls_per_day(
        base_count
    )
    for step in range(1, round(MAX_POLL_INTERVAL / POLL_INTERVAL_STEP) + 1):
        interval = step * POLL_INTERVAL_STEP
        if controller_calls_per_day(controller_count, interval) <= budget:
            return interval
    return None


class RachioControllerUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls a sprinkler controller for what is running now.

    Webhooks are the primary way state reaches Home Assistant. This coordinator
    is an opt-in fallback for installations that cannot receive webhooks.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        rachio: Rachio,
        config_entry: RachioConfigEntry,
        controller_id: str,
        interval_minutes: float,
    ) -> None:
        """Initialize the Rachio controller update coordinator."""
        self.rachio = rachio
        self.controller_id = controller_id
        self._resume_polling_at: datetime | None = None
        self._calls_remaining = 0
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} controller update coordinator",
            update_interval=timedelta(minutes=interval_minutes),
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the schedule or zone currently running on the controller."""
        if self._resume_polling_at:
            if dt_util.utcnow() < self._resume_polling_at:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="polling_paused",
                    translation_placeholders={
                        "remaining": str(self._calls_remaining),
                        "resume": dt_util.as_local(self._resume_polling_at).isoformat(
                            timespec="minutes"
                        ),
                    },
                )
            self._resume_polling_at = None
        try:
            response = await self.hass.async_add_executor_job(
                self.rachio.device.current_schedule, self.controller_id
            )
        except RequestException as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        self._pause_if_calls_running_out(response[0])
        status = int(response[0][KEY_STATUS])
        if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            )
        if not HTTPStatus.OK <= status < HTTPStatus.MULTIPLE_CHOICES:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={"status": str(status)},
            )
        data: dict[str, Any] = response[1] or {}
        return data

    @callback
    def _pause_if_calls_running_out(self, headers: dict[str, str]) -> None:
        """Stop polling until the API limit resets if few calls remain."""
        try:
            remaining = int(headers[HEADER_RATE_REMAINING])
            reset = dt_util.parse_datetime(headers[HEADER_RATE_RESET])
        except KeyError, ValueError:
            return
        if reset is None or remaining >= POLL_RESERVE_CALLS:
            return
        self._calls_remaining = remaining
        self._resume_polling_at = reset
