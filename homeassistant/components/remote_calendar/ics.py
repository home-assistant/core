"""Module for parsing ICS content.

This module exists to fix known issues where calendar providers return calendars
that do not follow rfcc5545. This module will attempt to fix the calendar and return
a valid calendar object.
"""

import datetime
import logging

from ical.calendar import Calendar
from ical.calendar_stream import IcsCalendarStream
from ical.compat import enable_compat_mode
from ical.event import Event
from ical.exceptions import CalendarParseError

from homeassistant.core import HomeAssistant

from . import same_day_dtend_compat

_LOGGER = logging.getLogger(__name__)


class InvalidIcsException(Exception):
    """Exception to indicate that the ICS content is invalid."""


_validator_patched = False


def _patch_event_validator() -> None:
    """Patch Event class to fix same-day DTEND when compat mode is enabled."""
    global _validator_patched
    
    if _validator_patched:
        return
    
    original_init = Event.__init__
    
    def patched_init(self, **data):
        """Patched init that fixes same-day DTEND when compat mode is enabled."""
        original_init(self, **data)
        
        # Apply same-day DTEND fix if compat mode is enabled
        if same_day_dtend_compat.is_same_day_dtend_compat_enabled():
            if isinstance(self.dtstart, datetime.date) and not isinstance(self.dtstart, datetime.datetime):
                if self.dtend and self.dtend == self.dtstart:
                    self.dtend = self.dtstart + datetime.timedelta(days=1)
    
    Event.__init__ = patched_init
    _validator_patched = True


def _compat_calendar_from_ics(ics: str) -> Calendar:
    """Parse the ICS content and return a Calendar object.

    This function is called in a separate thread to avoid blocking the event
    loop while loading packages or parsing the ICS content for large calendars.

    It uses the `enable_compat_mode` context manager to fix known issues with
    calendar providers that return invalid calendars.
    """
    _patch_event_validator()
    
    with enable_compat_mode(ics) as compat_ics, same_day_dtend_compat.enable_same_day_dtend_compat():
        return IcsCalendarStream.calendar_from_ics(compat_ics)


async def parse_calendar(hass: HomeAssistant, ics: str) -> Calendar:
    """Parse the ICS content and return a Calendar object."""
    try:
        return await hass.async_add_executor_job(_compat_calendar_from_ics, ics)
    except CalendarParseError as err:
        _LOGGER.error("Error parsing calendar information: %s", err.message)
        _LOGGER.debug("Additional calendar error detail: %s", str(err.detailed_error))
        raise InvalidIcsException(err.message) from err
