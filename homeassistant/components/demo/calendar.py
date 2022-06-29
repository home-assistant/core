"""Demo platform that has two fake binary sensors."""
from __future__ import annotations

import copy
import datetime

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEvent,
    CalendarEventDevice,
    get_date,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo Calendar platform."""
    add_entities(
        [
            DemoCalendar(calendar_data_future(), "Calendar 1"),
            DemoCalendar(calendar_data_current(), "Calendar 2"),
            LegacyDemoCalendar("Calendar 3"),
        ]
    )


def calendar_data_future() -> CalendarEvent:
    """Representation of a Demo Calendar for a future event."""
    one_hour_from_now = dt_util.now() + datetime.timedelta(minutes=30)
    return CalendarEvent(
        start=one_hour_from_now,
        end=one_hour_from_now + datetime.timedelta(minutes=60),
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
        self._name = name

    @property
    def event(self) -> CalendarEvent:
        """Return the next upcoming event."""
        return self._event

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    async def async_get_events(self, hass, start_date, end_date) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [self._event]


class LegacyDemoCalendar(CalendarEventDevice):
    """Calendar for exercising shim API."""

    def __init__(self, name):
        """Initialize demo calendar."""
        self._name = name
        one_hour_from_now = dt_util.now() + dt_util.dt.timedelta(minutes=30)
        self._event = {
            "start": {"dateTime": one_hour_from_now.isoformat()},
            "end": {
                "dateTime": (
                    one_hour_from_now + dt_util.dt.timedelta(minutes=60)
                ).isoformat()
            },
            "summary": "Future Event",
            "description": "Future Description",
            "location": "Future Location",
        }

    @property
    def event(self):
        """Return the next upcoming event."""
        return self._event

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    async def async_get_events(self, hass, start_date, end_date):
        """Get all events in a specific time frame."""
        event = copy.copy(self.event)
        event["title"] = event["summary"]
        event["start"] = get_date(event["start"]).isoformat()
        event["end"] = get_date(event["end"]).isoformat()
        return [event]
