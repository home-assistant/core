"""Library for working with CalDAV api."""

import asyncio

import caldav

from homeassistant.core import HomeAssistant


async def async_get_calendars(
    hass: HomeAssistant, client: caldav.DAVClient, component: str
) -> list[caldav.Calendar]:
    """Get all calendars that support the specified component."""
    calendars = await hass.async_add_executor_job(client.principal().calendars)
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
