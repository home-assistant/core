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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN as DOMAIN_RACHIO,
    KEY_ADDRESS,
    KEY_DURATION_SECONDS,
    KEY_ID,
    KEY_LOCALITY,
    KEY_PROGRAM_ID,
    KEY_PROGRAM_NAME,
    KEY_RUN_SUMMARIES,
    KEY_SKIP,
    KEY_SKIPPABLE,
    KEY_START_TIME,
    KEY_VALVE_NAME,
)
from .coordinator import RachioScheduleUpdateCoordinator
from .device import RachioPerson

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for Rachio smart hose timer calendar."""
    person: RachioPerson = hass.data[DOMAIN_RACHIO][config_entry.entry_id]
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
        self._attr_name = "Rachio Smart Hose Timer Events"
        self._attr_unique_id = f"{coordinator.base_station[KEY_ID]}-calendar"
        self.location = coordinator.base_station[KEY_ADDRESS][KEY_LOCALITY]

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
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

        start_time: Any = dt_util.parse_datetime(event[KEY_START_TIME])
        return CalendarEvent(
            summary=event[KEY_PROGRAM_NAME],
            start=dt_util.as_local(start_time),
            end=dt_util.as_local(start_time)
            + timedelta(seconds=int(event[KEY_RUN_SUMMARIES][0][KEY_DURATION_SECONDS])),
            description=event[KEY_RUN_SUMMARIES][0][KEY_VALVE_NAME],
            location=self.location,
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        if not self.coordinator.data:
            raise HomeAssistantError("No events scheduled")
        schedule = self.coordinator.data

        event_list: list[CalendarEvent] = []
        for run in schedule:
            start_time = dt_util.parse_datetime(run[KEY_START_TIME])
            if start_time:
                if (
                    start_date <= start_time <= end_date
                    and KEY_SKIP not in run[KEY_RUN_SUMMARIES][0]
                ):
                    event = CalendarEvent(
                        summary=run[KEY_RUN_SUMMARIES][0][KEY_VALVE_NAME],
                        start=start_time,
                        end=start_time
                        + timedelta(
                            seconds=int(run[KEY_RUN_SUMMARIES][0][KEY_DURATION_SECONDS])
                        ),
                        description=run[KEY_PROGRAM_NAME],
                        location=self.location,
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
        event = uid.split("/")
        program = event[0]
        timestamp = event[1]
        await self.hass.async_add_executor_job(
            self.base_station.create_skip, program, timestamp
        )
        await self.coordinator.async_refresh()
