"""Library for working with CalDAV api."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

import logging

import caldav
from caldav.lib.error import DAVError
import icalendar

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ASSUMED_COMPONENTS = frozenset({"VEVENT", "VTODO"})


async def async_get_calendars(
    hass: HomeAssistant, client: caldav.DAVClient, component: str
) -> list[caldav.Calendar]:
    """Get all calendars that support the specified component."""

    def _get_calendars() -> tuple[
        list[caldav.Calendar], list[tuple[str, str | None, str]]
    ]:
        calendars = []
        needs_warning: list[tuple[str, str | None, str]] = []
        for calendar in client.principal().calendars():
            try:
                supported_components = calendar.get_supported_components()
            except KeyError, DAVError:
                needs_warning.append((str(calendar.url), calendar.name, component))

                if component in ASSUMED_COMPONENTS:
                    # If the server does not specify supported components, we assume
                    # the calendar is supported for the requested component.
                    supported_components = [component]
                else:
                    supported_components = []

            if component in supported_components:
                calendars.append(calendar)
        return calendars, needs_warning

    calendars, needs_warning = await hass.async_add_executor_job(_get_calendars)

    if needs_warning:
        warned_calendars: set[tuple[str, str]] = hass.data.setdefault(
            DOMAIN, {}
        ).setdefault("warned_calendars", set())
        for url, name, comp in needs_warning:
            # This workaround and warning can be removed when we upgrade to caldav 3.0
            if (url, comp) not in warned_calendars:
                warned_calendars.add((url, comp))
                if comp in ASSUMED_COMPONENTS:
                    _LOGGER.warning(
                        "CalDAV server does not report supported"
                        " components for calendar %s, "
                        "assuming it supports the requested component '%s'",
                        name or url,
                        comp,
                    )
                else:
                    _LOGGER.warning(
                        "CalDAV server does not report supported"
                        " components for calendar %s. "
                        "Not assuming support for requested component '%s'",
                        name or url,
                        comp,
                    )

    return calendars


def get_attr_value(component: icalendar.cal.Component, attribute: str) -> str | None:
    """Return the value of an iCalendar component property as a string."""
    if (value := component.get(attribute.upper().replace("_", "-"))) is not None:
        return str(value.dt) if hasattr(value, "dt") else str(value)
    return None
