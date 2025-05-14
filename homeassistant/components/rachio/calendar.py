"""Rachio smart hose timer calendar."""

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    KEY_ADDRESS,
    KEY_DURATION_SECONDS,
    KEY_ID,
    KEY_LOCALITY,
    KEY_PROGRAM_ID,
    KEY_PROGRAM_NAME,
    KEY_RUN_SUMMARIES,
    KEY_SERIAL_NUMBER,
    KEY_SKIP,
    KEY_SKIPPABLE,
    KEY_START_TIME,
    KEY_TOTAL_RUN_DURATION,
    KEY_VALVE_NAME,
)
from .coordinator import RachioScheduleUpdateCoordinator
from .device import RachioPerson

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for Rachio smart hose timer calendar."""
    person: RachioPerson = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        RachioCalendarEntity(base_station.schedule_coordinator, base_station)
        for base_station in person.base_stations
    )


class RachioCalendarEntity(
    CoordinatorEntity[RachioScheduleUpdateCoordinator], CalendarEntity
):
    """Rachio calendar entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "calendar"
    _attr_supported_features = CalendarEntityFeature.DELETE_EVENT

    def __init__(
        self, coordinator: RachioScheduleUpdateCoordinator, base_station
    ) -> None:
        """Initialize a Rachio calendar entity."""
        super().__init__(coordinator)
        self.base_station = base_station
        self._event: CalendarEvent | None = None
        self._location = coordinator.base_station[KEY_ADDRESS][KEY_LOCALITY]
        self._attr_translation_placeholders = {
            "base": coordinator.base_station[KEY_SERIAL_NUMBER]
        }
        self._attr_unique_id = f"{coordinator.base_station[KEY_ID]}-calendar"
        self._previous_event: dict[str, Any] | None = None

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        if not (event := self._handle_upcoming_event()):
            return None
        start_time = dt_util.parse_datetime(event[KEY_START_TIME], raise_on_error=True)
        valves = ", ".join(
            [event[KEY_VALVE_NAME] for event in event[KEY_RUN_SUMMARIES]]
        )
        return CalendarEvent(
            summary=event[KEY_PROGRAM_NAME],
            start=dt_util.as_local(start_time),
            end=dt_util.as_local(start_time)
            + timedelta(seconds=int(event[KEY_TOTAL_RUN_DURATION])),
            description=valves,
            location=self._location,
        )

    def _handle_upcoming_event(self) -> dict[str, Any] | None:
        """Handle current or next event."""
        # Currently when an event starts, it disappears from the
        # API until the event ends. So we store the upcoming event and use
        # the stored version if it's within the event time window.
        if self._previous_event:
            start_time = dt_util.parse_datetime(
                self._previous_event[KEY_START_TIME], raise_on_error=True
            )
            end_time = start_time + timedelta(
                seconds=int(self._previous_event[KEY_TOTAL_RUN_DURATION])
            )
            if start_time <= dt_util.now() <= end_time:
                return self._previous_event

        schedule = iter(self.coordinator.data)
        event = next(schedule, None)
        if not event:  # Schedule is empty
            return None
        while (
            not event[KEY_SKIPPABLE] or KEY_SKIP in event[KEY_RUN_SUMMARIES][0]
        ):  # Not being skippable indicates the event is in the past
            event = next(schedule, None)
            if not event:  # Schedule only has past or skipped events
                return None
        self._previous_event = event  # Store for future use
        return event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        if not self.coordinator.data:
            raise HomeAssistantError("No events scheduled")
        schedule = self.coordinator.data
        event_list: list[CalendarEvent] = []

        for run in schedule:
            event_start = dt_util.as_local(
                dt_util.parse_datetime(run[KEY_START_TIME], raise_on_error=True)
            )
            if event_start > end_date:
                break
            if run[KEY_SKIPPABLE]:  # Future events
                event_end = event_start + timedelta(
                    seconds=int(run[KEY_TOTAL_RUN_DURATION])
                )
            else:  # Past events
                event_end = event_start + timedelta(
                    seconds=int(run[KEY_RUN_SUMMARIES][0][KEY_DURATION_SECONDS])
                )

            if (
                event_end > start_date
                and event_start < end_date
                and KEY_SKIP not in run[KEY_RUN_SUMMARIES][0]
            ):
                valves = ", ".join(
                    [event[KEY_VALVE_NAME] for event in run[KEY_RUN_SUMMARIES]]
                )
                event = CalendarEvent(
                    summary=run[KEY_PROGRAM_NAME],
                    start=event_start,
                    end=event_end,
                    description=valves,
                    location=self._location,
                    uid=f"{run[KEY_PROGRAM_ID]}/{run[KEY_START_TIME]}",
                )
                event_list.append(event)
        return event_list

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Skip an upcoming event on the calendar."""
        program, timestamp = uid.split("/")
        await self.hass.async_add_executor_job(
            self.base_station.create_skip, program, timestamp
        )
        await self.coordinator.async_refresh()
