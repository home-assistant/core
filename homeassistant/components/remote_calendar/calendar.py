"""Calendar platform for a Local Calendar."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging

from ical.calendar_stream import IcsCalendarStream
from ical.event import Event

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_CALENDAR_NAME
from .coordinator import RemoteCalendarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local calendar platform."""
    coordinator = entry.runtime_data

    name = entry.data[CONF_CALENDAR_NAME]
    entity = RemoteCalendarEntity(coordinator, name, unique_id=entry.entry_id)
    async_add_entities([entity], True)


class RemoteCalendarEntity(CalendarEntity):
    """A calendar entity backed by a local iCalendar file."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RemoteCalendarDataUpdateCoordinator,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize LocalCalendarEntity."""
        self._client = None
        self._calendar = IcsCalendarStream.calendar_from_ics(coordinator.data)
        self.coordinator = coordinator
        self._calendar_lock = asyncio.Lock()
        self._event: CalendarEvent | None = None
        self._etag = None
        self._track_fetch = None
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._update_interval = timedelta(minutes=15)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        events = self._calendar.timeline_tz(start_date.tzinfo).overlapping(
            start_date,
            end_date,
        )
        return [_get_calendar_event(event) for event in events]

    async def async_update(self) -> None:
        """Update entity state with the next upcoming event."""
        self._calendar = await self.hass.async_add_executor_job(
            IcsCalendarStream.calendar_from_ics, self.coordinator.data
        )
        now = dt_util.now()
        events = self._calendar.timeline_tz(now.tzinfo).active_after(now)
        if event := next(events, None):
            self._event = _get_calendar_event(event)
        else:
            self._event = None


def _get_calendar_event(event: Event) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""
    start: datetime | date
    end: datetime | date
    if isinstance(event.start, datetime) and isinstance(event.end, datetime):
        start = dt_util.as_local(event.start)
        end = dt_util.as_local(event.end)
        if (end - start) <= timedelta(seconds=0):
            end = start + timedelta(minutes=30)
    else:
        start = event.start
        end = event.end
        if (end - start) < timedelta(days=0):
            end = start + timedelta(days=1)

    return CalendarEvent(
        summary=event.summary,
        start=start,
        end=end,
        description=event.description,
        uid=event.uid,
        rrule=event.rrule.as_rrule_str() if event.rrule else None,
        recurrence_id=event.recurrence_id,
        location=event.location,
    )
