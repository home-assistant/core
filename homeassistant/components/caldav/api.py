"""Library for working with CalDAV api."""

import asyncio

import caldav

from homeassistant.core import HomeAssistant


async def async_get_calendars(
    hass: HomeAssistant, client: caldav.DAVClient, component: str
) -> list[caldav.Calendar]:
    """Get all calendars that support the specified component."""

    def _get_calendars() -> list[caldav.Calendar]:
        return client.principal().calendars()

    calendars = await hass.async_add_executor_job(_get_calendars)
    components_results = await asyncio.gather(
        *[
            hass.async_add_executor_job(calendar.get_supported_components)
            for calendar in calendars
        ]
    )
    return [
        calendar
        for calendar, supported_components in zip(calendars, components_results)
        if component in supported_components
    ]


def get_attr_value(obj: caldav.CalendarObjectResource, attribute: str) -> str | None:
    """Return the value of the CalDav object attribute if defined."""
    if hasattr(obj, attribute):
        return getattr(obj, attribute).value
    return None
