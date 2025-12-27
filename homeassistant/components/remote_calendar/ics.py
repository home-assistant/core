"""Module for parsing ICS content.

This module exists to fix known issues where calendar providers return calendars
that do not follow rfcc5545. This module will attempt to fix the calendar and return
a valid calendar object.
"""

import logging
import re
from datetime import date, timedelta

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.compat import enable_compat_mode
from ical.exceptions import CalendarParseError

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class InvalidIcsException(Exception):
    """Exception to indicate that the ICS content is invalid."""


def _fix_same_day_dtend(ics: str) -> str:
    """Fix same-day DTEND all-day events by adjusting DTEND to next day."""
    def fix_date(match):
        date_str = match.group(1)
        try:
            year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
            next_day = date(year, month, day) + timedelta(days=1)
            return f"DTSTART;VALUE=DATE:{date_str}\nDTEND;VALUE=DATE:{next_day:%Y%m%d}"
        except (ValueError, OverflowError):
            return match.group(0)
    
    return re.sub(
        r'DTSTART;VALUE=DATE:(\d{8})\s*\r?\n\s*DTEND;VALUE=DATE:\1',
        fix_date,
        ics
    )


def _compat_calendar_from_ics(ics: str) -> Calendar:
    """Parse the ICS content and return a Calendar object.

    This function is called in a separate thread to avoid blocking the event
    loop while loading packages or parsing the ICS content for large calendars.

    It uses the `enable_compat_mode` context manager to fix known issues with
    calendar providers that return invalid calendars, and also fixes same-day
    DTEND issues at parse time.
    """
    # Fix same-day DTEND issues before parsing
    fixed_ics = _fix_same_day_dtend(ics)
    
    with enable_compat_mode(fixed_ics) as compat_ics:
        return IcsCalendarStream.calendar_from_ics(compat_ics)


async def parse_calendar(hass: HomeAssistant, ics: str) -> Calendar:
    """Parse the ICS content and return a Calendar object."""
    try:
        return await hass.async_add_executor_job(_compat_calendar_from_ics, ics)
    except CalendarParseError as err:
        _LOGGER.error("Error parsing calendar information: %s", err.message)
        _LOGGER.debug("Additional calendar error detail: %s", str(err.detailed_error))
        raise InvalidIcsException(err.message) from err
