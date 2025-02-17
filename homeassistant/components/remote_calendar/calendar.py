"""Calendar platform for a Local Calendar."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import logging

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.event import Event

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.util import dt as dt_util

from .const import CONF_CALENDAR_NAME, DOMAIN
from .store import LocalCalendarStore

_LOGGER = logging.getLogger(__name__)

PRODID = "-//homeassistant.io//local_calendar 1.0//EN"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the local calendar platform."""
    store = hass.data[DOMAIN][config_entry.entry_id]
    ics = await store.async_load()
    calendar: Calendar = await hass.async_add_executor_job(
        IcsCalendarStream.calendar_from_ics, ics
    )
    calendar.prodid = PRODID

    name = config_entry.data[CONF_CALENDAR_NAME]
    entity = LocalCalendarEntity(store, calendar, name, unique_id=config_entry.entry_id)
    async_add_entities([entity], True)


class LocalCalendarEntity(CalendarEntity):
    """A calendar entity backed by a local iCalendar file."""

    _attr_has_entity_name = True

    def __init__(
        self,
        store: LocalCalendarStore,
        calendar: Calendar,
        name: str,
        unique_id: str,
    ) -> None:
        """Initialize LocalCalendarEntity."""
        self._store = store
        self._client = None
        self._calendar = calendar
        self._calendar_lock = asyncio.Lock()
        self._event: CalendarEvent | None = None
        self._etag = None
        self._track_fetch = None
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._update_interval = timedelta(minutes=15)
        # self._url = "https://www2.awrm.de/WasteManagementRemsmurr/WasteManagementServiceServlet?ApplicationName=Calendar&SubmitAction=sync&StandortID=1036699001&AboID=284134&Fra=Gelb;Papier;RestTonne2wo"
        self._url = "https://calendar.google.com/calendar/ical/p07n98go11onamd08d0kmq6jhs%40group.calendar.google.com/public/basic.ics"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        return self._event

    async def _fetch_calendar_and_update(self):
        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag
        res = await self._client.get(self._url, headers=headers)
        if res.status_code == 304:  # Not modified
            return
        res.raise_for_status()
        self._etag = res.headers.get("ETag")
        self._calendar = await self.hass.async_add_executor_job(
            IcsCalendarStream.calendar_from_ics, res.text
        )
        _LOGGER.debug("self._calendar %s", self._calendar)
        self._calendar.prodid = PRODID
        content = await self.hass.async_add_executor_job(
            IcsCalendarStream.calendar_to_ics, self._calendar
        )
        _LOGGER.debug("content %s", content)
        await self._store.async_store(content)

    async def async_added_to_hass(self) -> None:
        """Once initialized, get the calendar, and schedule future updates."""
        self._client = get_async_client(self.hass)
        self.hass.loop.create_task(self._fetch_calendar_and_update())
        self._track_fetch = async_track_time_interval(
            self.hass,
            lambda now: self.hass.loop.create_task(self._fetch_calendar_and_update()),
            self._update_interval,
        )

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
        now = dt_util.now()
        events = self._calendar.timeline_tz(now.tzinfo).active_after(now)
        if event := next(events, None):
            self._event = _get_calendar_event(event)
        else:
            self._event = None

    async def _async_store(self) -> None:
        """Persist the calendar to disk."""
        content = IcsCalendarStream.calendar_to_ics(self._calendar)
        await self._store.async_store(content)


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
