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
    'maxResults': 1,
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

    return [GoogleCalendar(hass, calendar_service, data, discovery_info[CONF_CAL_ID])
        for data in discovery_info[CONF_ENTITIES] if data[CONF_TRACK]]


class GoogleCalendar(Calendar):

    def __init__(self, hass, calendar_service, data, calendar_id):
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self.search = data.get('search', None)
        self.events = [
            {'start': dt.now(),
            'end': dt.now(),
            'text': 'bla'}
        ]

        super().__init__(hass, data.get('name', DOMAIN))

    @asyncio.coroutine
    def async_get_events(self):
        return self.events

    @asyncio.coroutine
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def async_update(self):
        _LOGGER.info('Update G calendar')

        #
        #service = self.calendar_service.get()
 #       params = dict(DEFAULT_GOOGLE_SEARCH_PARAMS)
  #      params['timeMin'] = dt.now().isoformat('T')
   #     params['calendarId'] = self.calendar_id

    #    events = service.events()
     #   result = events.list(**params).execute()

      #  _LOGGER.info('Finding events: %s', result)

       # items = result.get('items', [])
        #self.events = items
