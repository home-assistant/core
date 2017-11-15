"""
Support for Google Calendar Search binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.google_calendar/
"""
# pylint: disable=import-error
import logging
import asyncio

from datetime import timedelta, datetime


from homeassistant.components.calendar import Calendar, CalendarEvent
from homeassistant.components.google import (
    GoogleCalendarService, TOKEN_FILE, CONF_TRACK, CONF_ENTITIES, CONF_CAL_ID)
from homeassistant.util import Throttle, dt

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'GoogleCalendar'

DEFAULT_GOOGLE_SEARCH_PARAMS = {
    'orderBy': 'startTime',
    'singleEvents': True,
}


MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


def setup_platform(hass, config, add_devices, disc_info=None):
    """Set up the calendar platform for event devices."""
    if disc_info is None:
        return

    if not any(data[CONF_TRACK] for data in disc_info[CONF_ENTITIES]):
        return

    calendar_service = GoogleCalendarService(hass.config.path(TOKEN_FILE))

    add_devices([GoogleCalendar(hass, calendar_service,
                                data, disc_info[CONF_CAL_ID])
                 for data in disc_info[CONF_ENTITIES] if data[CONF_TRACK]])


class GoogleCalendar(Calendar):
    """Entity for Google Calendar events."""

    def __init__(self, hass, calendar_service, data, calendar_id):
        """Initialze Google Calendar entity."""
        self.calendar_service = calendar_service
        self.calendar_id = calendar_id
        self.search = data.get('search', None)
        self._events = []

        self._name = data.get('name', DOMAIN)
        self._next_event = None

        self.refresh_events()

    @property
    def name(self):
        """Return the name of the calendar."""
        return self._name

    @property
    def next_event(self):
        """Return the next occuring event."""
        return self._next_event

    @asyncio.coroutine
    def async_get_events(self):
        """Return a list of events."""
        return self._events

    @asyncio.coroutine
    def async_update(self):
        """Update Calendar."""
        self.refresh_events()
        self._next_event = self.update_next_event()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def refresh_events(self):
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

        items = result.get('items', [])

        self._events = [GoogleCalendarEvent(item) for item in items]
        self._events.sort(key=lambda event: event.start)


class GoogleCalendarEvent(CalendarEvent):
    """class for creating google events."""

    def __init__(self, event):
        """Initialize google event."""
        self._start = self.convertDatetime(event['start'])
        self._end = self.convertDatetime(event['end'])
        self._message = event['summary']

        self._location = event.get('location', None)

    @property
    def location(self):
        """Return location of the event."""
        return self._location

    def convertDatetime(self, dateObject):
        """Convert dateTime returned from Google."""
        dateString = dateObject['dateTime']
        if ":" == dateString[-3:-2]:
            dateString = dateString[:-3]+dateString[-2:]
        return datetime.strptime(dateString, '%Y-%m-%dT%H:%M:%S%z')
