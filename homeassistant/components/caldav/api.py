"""Library for working with CalDAV api."""

from typing import cast

from caldav.calendarobjectresource import CalendarObjectResource
from caldav.collection import Calendar
from caldav.davclient import DAVClient
from caldav.elements import ical

from homeassistant.core import HomeAssistant


async def async_get_calendars(
    hass: HomeAssistant, client: DAVClient, component: str
) -> list[tuple[Calendar, str | None]]:
    """Get all calendars that support the specified component."""

    def _get_calendars() -> list[tuple[Calendar, str | None]]:
        calendars = cast(list[Calendar], client.get_principal().get_calendars())
        return [
            (calendar, cast(str | None, calendar.get_display_name()))
            for calendar in calendars
            if component in cast(list[str], calendar.get_supported_components())
        ]

    return await hass.async_add_executor_job(_get_calendars)


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
