"""Library for working with CalDAV api."""

from datetime import datetime
from typing import NamedTuple, cast

from caldav.calendarobjectresource import CalendarObjectResource, FreeBusy
from caldav.collection import Calendar
from caldav.davclient import DAVClient
from caldav.elements import ical
from icalendar import FBTYPE

from homeassistant.core import HomeAssistant


class CalDavCalendar(NamedTuple):
    """A calendar with its name and the components it supports."""

    calendar: Calendar
    name: str | None
    components: list[str]


class BusyPeriod(NamedTuple):
    """A span of time in which a calendar is busy."""

    start: datetime
    end: datetime


def get_calendars(client: DAVClient, components: set[str]) -> list[CalDavCalendar]:
    """Get the calendars that support any of the components, with their name."""
    calendars = []
    for calendar in cast(list[Calendar], client.get_principal().get_calendars()):
        supported = cast(list[str], calendar.get_supported_components())
        if components.intersection(supported):
            name = cast(str | None, calendar.get_display_name())
            calendars.append(CalDavCalendar(calendar, name, supported))
    return calendars


def calendars_supporting(
    calendars: list[CalDavCalendar], component: str
) -> list[tuple[Calendar, str | None]]:
    """Return the calendars that support the specified component."""
    return [
        (calendar.calendar, calendar.name)
        for calendar in calendars
        if component in calendar.components
    ]


async def async_get_calendars(
    hass: HomeAssistant, client: DAVClient, component: str
) -> list[tuple[Calendar, str | None]]:
    """Get all calendars that support the specified component."""
    calendars = await hass.async_add_executor_job(get_calendars, client, {component})
    return calendars_supporting(calendars, component)


async def async_get_calendar_color(
    hass: HomeAssistant, calendar: Calendar
) -> str | None:
    """Get the color of a calendar, None if it has none."""
    color = cast(
        str | None,
        await hass.async_add_executor_job(calendar.get_property, ical.CalendarColor()),
    )
    # Apple Calendar, DAVx5 and SOGo append an alpha channel.
    if color and color.startswith("#") and len(color) == 9:
        return color[:7]
    return color


def get_attr_value(obj: CalendarObjectResource, attribute: str) -> str | None:
    """Return the value of the CalDav object attribute if defined."""
    if hasattr(obj, attribute):
        return getattr(obj, attribute).value
    return None


def _busy_periods(
    free_busy: FreeBusy, start: datetime, end: datetime
) -> list[BusyPeriod]:
    """Return the busy periods within a time range, sorted and merged."""
    found: list[BusyPeriod] = []
    for component in free_busy.icalendar_instance.walk("VFREEBUSY"):
        periods = component.get("FREEBUSY")
        if periods is None:
            # Radicale answers with one VFREEBUSY per span and its type in FBTYPE.
            if str(component.get("FBTYPE", "")).upper().startswith("BUSY"):
                found.append(
                    BusyPeriod(component.decoded("DTSTART"), component.decoded("DTEND"))
                )
            continue
        found.extend(
            BusyPeriod(period.start, period.end)
            for period in (periods if isinstance(periods, list) else [periods])
            if period.FBTYPE != FBTYPE.FREE
        )
    merged: list[BusyPeriod] = []
    for found_start, found_end in sorted(found):
        period = BusyPeriod(max(found_start, start), min(found_end, end))
        if period.start >= period.end:
            continue
        if merged and period.start <= merged[-1].end:
            merged[-1] = BusyPeriod(merged[-1].start, max(merged[-1].end, period.end))
        else:
            merged.append(period)
    return merged


def get_busy_periods(
    calendar: Calendar, start: datetime, end: datetime
) -> list[BusyPeriod]:
    """Ask the server when a calendar is busy (RFC 4791 section 7.10)."""
    return _busy_periods(
        cast(FreeBusy, calendar.freebusy_request(start, end)), start, end
    )
