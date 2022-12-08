"""Calendar platform for a Local Calendar."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.event import Event
from ical.store import EventStore
from ical.types import Range, Recur

from homeassistant.components.calendar import (
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_RRULE,
    EVENT_START,
    EVENT_SUMMARY,
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_CALENDAR_NAME, DOMAIN
from .store import LocalCalendarStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local calendar platform."""
    store = hass.data[DOMAIN][config_entry.entry_id]
    ics = await store.async_load()
    calendar = IcsCalendarStream.calendar_from_ics(ics)

    name = config_entry.data[CONF_CALENDAR_NAME]
    entity = LocalCalendarEntity(store, calendar, name, unique_id=config_entry.entry_id)
    async_add_entities([entity], True)


class LocalCalendarEntity(CalendarEntity):
    """A calendar entity backed by a local iCalendar file."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    )

    def __init__(
        self,
        store: LocalCalendarStore,
        calendar: Calendar,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize LocalCalendarEntity."""
        self._store = store
        self._calendar = calendar
        self._event: CalendarEvent | None = None
        self._attr_name = name.capitalize()
        self._attr_unique_id = unique_id

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get all events in a specific time frame."""
        events = self._calendar.timeline_tz(dt_util.DEFAULT_TIME_ZONE).overlapping(
            dt_util.as_local(start_date),
            dt_util.as_local(end_date),
        )
        return [_get_calendar_event(event) for event in events]

    async def async_update(self) -> None:
        """Update entity state with the next upcoming event."""
        events = self._calendar.timeline_tz(dt_util.DEFAULT_TIME_ZONE).active_after(
            dt_util.now()
        )
        if event := next(events, None):
            self._event = _get_calendar_event(event)
        else:
            self._event = None

    async def _async_store(self) -> None:
        """Persist the calendar to disk."""
        content = IcsCalendarStream.calendar_to_ics(self._calendar)
        await self._store.async_store(content)

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a new event to calendar."""
        event = Event.parse_obj(
            {
                EVENT_SUMMARY: kwargs[EVENT_SUMMARY],
                EVENT_START: kwargs[EVENT_START],
                EVENT_END: kwargs[EVENT_END],
                EVENT_DESCRIPTION: kwargs.get(EVENT_DESCRIPTION),
            }
        )
        if rrule := kwargs.get(EVENT_RRULE):
            event.rrule = Recur.from_rrule(rrule)

        EventStore(self._calendar).add(event)
        await self._async_store()
        await self.async_update_ha_state(force_refresh=True)

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete an event on the calendar."""
        range_value: Range = Range.NONE
        if recurrence_range == Range.THIS_AND_FUTURE:
            range_value = Range.THIS_AND_FUTURE
        EventStore(self._calendar).delete(
            uid,
            recurrence_id=recurrence_id,
            recurrence_range=range_value,
        )
        await self._async_store()
        await self.async_update_ha_state(force_refresh=True)


def _get_calendar_event(event: Event) -> CalendarEvent:
    """Return a CalendarEvent from an API event."""
    return CalendarEvent(
        summary=event.summary,
        start=event.start,
        end=event.end,
        description=event.description,
        uid=event.uid,
        rrule=event.rrule.as_rrule_str() if event.rrule else None,
        recurrence_id=event.recurrence_id,
    )
