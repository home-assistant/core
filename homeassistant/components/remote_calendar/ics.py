"""Module for parsing ICS content.

This module exists to fix known issues where calendar providers return calendars
that do not follow rfcc5545. This module will attempt to fix the calendar and return
a valid calendar object.
"""

import logging

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class InvalidIcsException(Exception):
    """Exception to indicate that the ICS content is invalid."""


def _make_compat(ics: str) -> str:
    """Make the ICS content compatible with the parser."""
    # Office 365 returns a calendar with a TZID that is not valid and does not meet
    # rfc5545. Remove the invalid TZID from the calendar so that it can be parsed correctly.
    return ics.replace(";TZID=Customized Time Zone", "")


async def parse_calendar(hass: HomeAssistant, ics: str) -> Calendar:
    """Parse the ICS content and return a Calendar object."""

    ics = _make_compat(ics)

    # calendar_from_ics will dynamically load packages the first time it is called, so we need
    # to do it in a separate thread to avoid blocking the event loop
    try:
        return await hass.async_add_executor_job(
            IcsCalendarStream.calendar_from_ics, ics
        )
    except CalendarParseError as err:
        _LOGGER.error("Error parsing calendar information: %s", err.message)
        _LOGGER.debug("Additional calendar error detail: %s", str(err.detailed_error))
        raise InvalidIcsException(err.message) from err
