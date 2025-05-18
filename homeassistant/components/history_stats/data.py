"""Manage the history_stats data."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
import math

from homeassistant.components.recorder import get_instance, history
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util

from .helpers import async_calculate_period, floored_timestamp

MIN_TIME_UTC = datetime.datetime.min.replace(tzinfo=dt_util.UTC)

_LOGGER = logging.getLogger(__name__)


@dataclass
class HistoryStatsState:
    """The current stats of the history stats."""

    seconds_matched: float | None
    match_count: int | None
    period: tuple[datetime.datetime, datetime.datetime]


@dataclass
class HistoryState:
    """A minimal state to avoid holding on to State objects."""

    state: str
    last_changed: float


class HistoryStats:
    """Manage history stats."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        entity_states: list[str],
        start: Template | None,
        end: Template | None,
        duration: datetime.timedelta | None,
    ) -> None:
        """Init the history stats manager."""
        self.hass = hass
        self.entity_id = entity_id
        self._period = (MIN_TIME_UTC, MIN_TIME_UTC)
        self._state: HistoryStatsState = HistoryStatsState(None, None, self._period)
        self._history_current_period: list[HistoryState] = []
        self._has_recorder_data = False
        self._entity_states = set(entity_states)
        self._duration = duration
        self._start = start
        self._end = end

        self._pending_events: list[Event[EventStateChangedData]] = []
        self._query_count = 0

    async def async_update(
        self, event: Event[EventStateChangedData] | None
    ) -> HistoryStatsState:
        """Update the stats at a given time."""
        # Get previous values of start and end
        previous_period_start, previous_period_end = self._period
        # Parse templates
        self._period = async_calculate_period(self._duration, self._start, self._end)
        # Get the current period
        current_period_start, current_period_end = self._period

        # Convert times to UTC
        current_period_start = dt_util.as_utc(current_period_start)
        current_period_end = dt_util.as_utc(current_period_end)
        previous_period_start = dt_util.as_utc(previous_period_start)
        previous_period_end = dt_util.as_utc(previous_period_end)

        # Compute integer timestamps
        current_period_start_timestamp = floored_timestamp(current_period_start)
        current_period_end_timestamp = floored_timestamp(current_period_end)
        previous_period_start_timestamp = floored_timestamp(previous_period_start)
        previous_period_end_timestamp = floored_timestamp(previous_period_end)
        utc_now = dt_util.utcnow()
        now_timestamp = floored_timestamp(utc_now)

        if event:
            self._pending_events.append(event)

        if current_period_start_timestamp > now_timestamp:
            # History cannot tell the future
            self._history_current_period = []
            self._has_recorder_data = False
            self._state = HistoryStatsState(None, None, self._period)
            return self._state
        #
        # We avoid querying the database if the below did NOT happen:
        #
        # - No previous run occurred (uninitialized)
        # - The start time moved back in time
        # - The end time moved back in time
        # - The previous period ended before now
        #
        if (
            self._has_recorder_data
            and current_period_start_timestamp >= previous_period_start_timestamp
            and (
                current_period_end_timestamp == previous_period_end_timestamp
                or (
                    current_period_end_timestamp >= previous_period_end_timestamp
                    and previous_period_end_timestamp <= now_timestamp
                )
            )
        ):
            start_changed = (
                current_period_start_timestamp != previous_period_start_timestamp
            )
            end_changed = current_period_end_timestamp != previous_period_end_timestamp
            if start_changed:
                self._prune_history_cache(current_period_start_timestamp)

            new_data = False
            if event and (new_state := event.data["new_state"]) is not None:
                if current_period_start_timestamp <= floored_timestamp(
                    new_state.last_changed
                ):
                    self._history_current_period.append(
                        HistoryState(new_state.state, new_state.last_changed_timestamp)
                    )
                    new_data = True
            if (
                not new_data
                and current_period_end_timestamp < now_timestamp
                and not start_changed
                and not end_changed
            ):
                # If period has not changed and current time after the period end...
                # Don't compute anything as the value cannot have changed
                return self._state
        else:
            await self._async_history_from_db(
                current_period_start_timestamp, now_timestamp
            )
            for pending_event in self._pending_events:
                if (new_state := pending_event.data["new_state"]) is not None:
                    if current_period_start_timestamp <= floored_timestamp(
                        new_state.last_changed
                    ):
                        self._history_current_period.append(
                            HistoryState(
                                new_state.state, new_state.last_changed_timestamp
                            )
                        )

            self._has_recorder_data = True

        if self._query_count == 0:
            self._pending_events = []

        seconds_matched, match_count = self._async_compute_seconds_and_changes(
            now_timestamp,
            current_period_start_timestamp,
            current_period_end_timestamp,
        )
        self._state = HistoryStatsState(seconds_matched, match_count, self._period)
        return self._state

    async def _async_history_from_db(
        self,
        current_period_start_timestamp: float,
        current_period_end_timestamp: float,
    ) -> None:
        """Update history data for the current period from the database."""
        self._query_count += 1
        try:
            instance = get_instance(self.hass)
            states = await instance.async_add_executor_job(
                self._state_changes_during_period,
                current_period_start_timestamp,
                current_period_end_timestamp,
            )
        finally:
            self._query_count -= 1
        self._history_current_period = [
            HistoryState(state.state, state.last_changed.timestamp())
            for state in states
        ]

    def _state_changes_during_period(
        self, start_ts: float, end_ts: float
    ) -> list[State]:
        """Return state changes during a period."""
        start = dt_util.utc_from_timestamp(start_ts)
        end = dt_util.utc_from_timestamp(end_ts)
        return history.state_changes_during_period(
            self.hass,
            start,
            end,
            self.entity_id,
            include_start_time_state=True,
            no_attributes=True,
        ).get(self.entity_id, [])

    def _async_compute_seconds_and_changes(
        self, now_timestamp: float, start_timestamp: float, end_timestamp: float
    ) -> tuple[float, int]:
        """Compute the seconds matched and changes from the history list and first state."""
        # state_changes_during_period is called with include_start_time_state=True
        # which is the default and always provides the state at the start
        # of the period
        previous_state_matches = False
        last_state_change_timestamp = 0.0
        elapsed = 0.0
        match_count = 0

        # Make calculations
        for history_state in self._history_current_period:
            current_state_matches = history_state.state in self._entity_states
            state_change_timestamp = history_state.last_changed

            if math.floor(state_change_timestamp) > end_timestamp:
                break

            if math.floor(state_change_timestamp) > now_timestamp:
                # Shouldn't count states that are in the future
                _LOGGER.debug(
                    "Skipping future timestamp %s (now %s)",
                    state_change_timestamp,
                    now_timestamp,
                )
                break

            if previous_state_matches:
                elapsed += state_change_timestamp - last_state_change_timestamp
            elif current_state_matches:
                match_count += 1

            previous_state_matches = current_state_matches
            last_state_change_timestamp = max(start_timestamp, state_change_timestamp)

        # Count time elapsed between last history state and end of measure
        if previous_state_matches:
            measure_end = min(end_timestamp, now_timestamp)
            elapsed += measure_end - last_state_change_timestamp

        # Save value in seconds
        seconds_matched = elapsed
        return seconds_matched, match_count

    def _prune_history_cache(self, start_timestamp: float) -> None:
        """Remove unnecessary old data from the history state cache from previous runs.

        Update the timestamp of the last record from before the start to the current start time.
        """
        trim_count = 0
        for i, history_state in enumerate(self._history_current_period):
            if history_state.last_changed >= start_timestamp:
                break
            history_state.last_changed = start_timestamp
            if i > 0:
                trim_count += 1
        if trim_count:  # Don't slice if no data was removed
            self._history_current_period = self._history_current_period[trim_count:]
