"""Demo platform that has two fake binary sensors."""
from __future__ import annotations

import datetime

from homeassistant.components.calendar import CalendarEvent, CalendarEventDevice
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
            DemoGoogleCalendar(hass, calendar_data_future(), "Calendar 1"),
            DemoGoogleCalendar(hass, calendar_data_current(), "Calendar 2"),
        ]
    )


def calendar_data_future() -> CalendarEvent:
    """Representation of a Demo Calendar for a future event."""
    one_hour_from_now = dt_util.now() + datetime.timedelta(minutes=30)
    return CalendarEvent(
        start=one_hour_from_now,
        end=one_hour_from_now + datetime.timedelta(minutes=60),
        summary="Future Event",
    )


def calendar_data_current() -> CalendarEvent:
    """Representation of a Demo Calendar for a current event."""
    middle_of_event = dt_util.now() - datetime.timedelta(minutes=30)
    return CalendarEvent(
        start=middle_of_event,
        end=middle_of_event + datetime.timedelta(minutes=60),
        summary="Current Event",
    )


class DemoGoogleCalendar(CalendarEventDevice):
    """Representation of a Demo Calendar element."""

    def __init__(self, hass: HomeAssistant, event: CalendarEvent, name: str) -> None:
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
