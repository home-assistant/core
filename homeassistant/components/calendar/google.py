"""
Support for Google Calendar Search binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.google_calendar/
"""
# pylint: disable=import-error
import logging
import asyncio

from datetime import timedelta


import homeassistant.util.dt as dt
from homeassistant.components.calendar import Calendar
from homeassistant.components.google import (
    GoogleCalendarService, TOKEN_FILE, CONF_TRACK, CONF_ENTITIES, CONF_CAL_ID)

from homeassistant.util import Throttle

DOMAIN = 'GoogleCalendar'

DEFAULT_GOOGLE_SEARCH_PARAMS = {
    'orderBy': 'startTime',
    'singleEvents': True,
}


MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=2)

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_get_handler(hass, config, discovery_info=None):
    """Set up the calendar platform for event devices."""
    if discovery_info is None:
        return []

    if not any(data[CONF_TRACK] for data in discovery_info[CONF_ENTITIES]):
        return []

    calendar_service = GoogleCalendarService(hass.config.path(TOKEN_FILE))

    return [GoogleCalendar(hass, calendar_service, data,
                           discovery_info[CONF_CAL_ID])
            for data in discovery_info[CONF_ENTITIES] if data[CONF_TRACK]]


class GoogleCalendar(Calendar):
    """Entity for Google Calendar events."""

    def __init__(self, hass, calendar_service, data, calendar_id):
        """Initialze Google Calendar entity."""
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self.search = data.get('search', None)
        self.events = []

        super().__init__(hass, data.get('name', DOMAIN))

    @asyncio.coroutine
    def async_get_events(self):
        """Return a list of events."""
        return self.events

    @asyncio.coroutine
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def async_update(self):
        """Update list of event."""
        service = self.calendar_service.get()
        params = dict(DEFAULT_GOOGLE_SEARCH_PARAMS)
        params['timeMin'] = dt.now().replace(day=1,
                                             minute=0,
                                             hour=0).isoformat('T')

        end = dt.now() + dt.dt.timedelta(weeks=8)

        params['timeMax'] = end.replace(day=1, minute=0, hour=0).isoformat('T')
        params['calendarId'] = self.calendar_id

        events = service.events()
        result = events.list(**params).execute()

        _LOGGER.info('Finding events: %s', result)

        items = result.get('items', [])
        self.events = items
