"""Library for working with CalDAV api."""

import logging

import caldav

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_get_calendars(
    hass: HomeAssistant, client: caldav.DAVClient, component: str
) -> list[caldav.Calendar]:
    """Get all calendars that support the specified component."""

    def _get_calendars() -> list[caldav.Calendar]:
        calendars = []
        for calendar in client.principal().calendars():
            try:
                supported_components = calendar.get_supported_components()
            except KeyError:
                if component in ("VEVENT", "VTODO"):
                    _LOGGER.warning(
                        "CalDAV server does not report supported components for calendar %s, "
                        "assuming it supports the requested component '%s'",
                        calendar.name,
                        component,
                    )
                    # If the server does not specify supported components, we assume
                    # the calendar is supported for the requested component.
                    supported_components = [component]
                else:
                    _LOGGER.warning(
                        "CalDAV server does not report supported components for calendar %s. "
                        "Not assuming support for requested component '%s'",
                        calendar.name,
                        component,
                    )
                    supported_components = []

            if component in supported_components:
                calendars.append(calendar)
        return calendars

    return await hass.async_add_executor_job(_get_calendars)


def get_attr_value(obj: caldav.CalendarObjectResource, attribute: str) -> str | None:
    """Return the value of the CalDav object attribute if defined."""
    if hasattr(obj, attribute):
        return getattr(obj, attribute).value
    return None
