"""
Support for Google Calendar Search binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.google_calendar/
"""
# pylint: disable=import-error
import logging
import asyncio

from datetime import timedelta

from homeassistant.components.calendar import Calendar
from homeassistant.components.google import GoogleCalendarService, TOKEN_FILE

from homeassistant.util import Throttle

DOMAIN = 'GoogleCalendar'

DEFAULT_GOOGLE_SEARCH_PARAMS = {
    'orderBy': 'startTime',
    'maxResults': 1,
    'singleEvents': True,
}


MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=2)

_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_get_handler(hass, config, async_add_devices, discovery_info=None):
    calendar_service = GoogleCalendarService(hass.config.path(TOKEN_FILE))
    return GoogleCalendar(hass, DOMAIN, calendar_service)


class GoogleCalendar(Calendar):

    def __init__(self, hass, name, calendar_service):
        self.calendar_service = calendar_service
        self.calendar_id = 'hj3i0ucmkenfjmdbrr85v7o2q8@group.calendar.google.com'
        self.events = []

        super().__init__(hass, name)

    @asyncio.coroutine
    def async_get_events(self):
        return self.events

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    @asyncio.coroutine
    def async_update(self):
        service = self.calendar_service.get()
        params = dict(DEFAULT_GOOGLE_SEARCH_PARAMS)
        params['timeMin'] = dt.now().isoformat('T')
        params['calendarId'] = self.calendar_id

        events = service.events()
        result = events.list(**params).execute()

        _LOGGER.info('Finding events: %s', result)

        items = result.get('items', [])
        self.events = items
