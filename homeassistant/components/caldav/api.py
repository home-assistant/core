"""Library for working with CalDAV api."""

from typing import NamedTuple, cast

from caldav.calendarobjectresource import CalendarObjectResource
from caldav.collection import Calendar
from caldav.davclient import DAVClient
from caldav.elements import ical

from homeassistant.core import HomeAssistant


class CalDavCalendar(NamedTuple):
    """A calendar with its name and the components it supports."""

    calendar: Calendar
    name: str | None
    components: list[str]


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
