"""Creates a switch entity for the mower."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from ical.calendar import Calendar
from ical.event import Event
from ical.types.recur import Recur

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lawn mower platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AutomowerCalendarEntity(mower_id, coordinator) for mower_id in coordinator.data
    )


class AutomowerCalendarEntity(AutomowerBaseEntity, CalendarEntity):
    """Representation of the Automower Calendar element."""

    _attr_name: str | None = None

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        # calendar: Calendar,
    ) -> None:
        """Set up HusqvarnaAutomowerEntity."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = mower_id
        self._event: CalendarEvent | None = None
        # self.calendar = calendar
        self.calendar = Calendar()

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        # now = dt_util.now()
        # _LOGGER.debug("now: %s ", now)
        # events = self.calendar.timeline_tz(now.tzinfo).active_after(now)
        # _LOGGER.debug("events: %s ", events)
        # return _get_calendar_event(self.mower_attributes.calendar.events[0])
        # if event := next(events, None):
        #     self._event = _get_calendar_event(event)
        # else:
        #     self._event = None
        # return self._event

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        schedule_no: dict = {}
        for event in self.mower_attributes.calendar.events:
            if event.work_area_id is not None:
                schedule_no[event.work_area_id] = 0
            if event.work_area_id is None:
                schedule_no["-1"] = 0

        for event in self.mower_attributes.calendar.events:
            wa_name = ""
            if event.work_area_id is not None:
                if self.mower_attributes.work_areas is not None:
                    _work_areas = self.mower_attributes.work_areas
                    wa_name = f"{_work_areas[event.work_area_id].name} "
                    schedule_no[event.work_area_id] = (
                        schedule_no[event.work_area_id] + 1
                    )
                    number = schedule_no[event.work_area_id]
            if event.work_area_id is None:
                schedule_no["-1"] = schedule_no["-1"] + 1
                number = schedule_no["-1"]
            self.calendar.events.append(
                Event(
                    dtstart=event.start,
                    dtend=event.end,
                    rrule=Recur.from_rrule(event.rrule),
                    summary=f"{wa_name}Schedule {number}",
                )
            )
        events = self.calendar.timeline_tz(start_date.tzinfo).overlapping(
            start_date,
            end_date,
        )
        test = [_get_calendar_event(event) for event in events]
        _LOGGER.debug("test: %s ", test)
        return [_get_calendar_event(event) for event in events]

    async def async_update(self) -> None:
        """Update entity state with the next upcoming event."""
        now = dt_util.now()
        _LOGGER.debug("now: %s ", now)
        events = self.calendar.timeline_tz(now.tzinfo).active_after(now)
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
    )
