"""Demo platform that has two fake calendars."""
from __future__ import annotations

import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo Calendar config entry."""
    async_add_entities(
        [
            DemoCalendar(calendar_data_future(), "Calendar 1"),
            DemoCalendar(calendar_data_current(), "Calendar 2"),
        ]
    )


def calendar_data_future() -> CalendarEvent:
    """Representation of a Demo Calendar for a future event."""
    half_hour_from_now = dt_util.now() + datetime.timedelta(minutes=30)
    return CalendarEvent(
        start=half_hour_from_now,
        end=half_hour_from_now + datetime.timedelta(minutes=60),
        summary="Future Event",
        description="Future Description",
        location="Future Location",
    )


def calendar_data_current() -> CalendarEvent:
    """Representation of a Demo Calendar for a current event."""
    middle_of_event = dt_util.now() - datetime.timedelta(minutes=30)
    return CalendarEvent(
        start=middle_of_event,
        end=middle_of_event + datetime.timedelta(minutes=60),
        summary="Current Event",
    )


class DemoCalendar(CalendarEntity):
    """Representation of a Demo Calendar element."""

    def __init__(self, event: CalendarEvent, name: str) -> None:
        """Initialize demo calendar."""
        self._event = event
        self._attr_name = name

    @property
    def event(self) -> CalendarEvent:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        assert start_date < end_date
        if self._event.start_datetime_local >= end_date:
            return []
        if self._event.end_datetime_local < start_date:
            return []
        return [self._event]
