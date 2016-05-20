"""
Support for Google Calendar event device sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/calendar/

To exted this define a class that inherits from CalendarEventDevice
and implement get_next_event()
This should return either
dict: {
    'summary': str  # required, will have offset/search info removed,
    'description: str  # optional, default '',
    'location', str  # optional, default '',
    'start': date || dateTime as str,
    'end' date || dateTime as str,
}  # can contain more but won't be used
or
None # if no events are found
"""
import logging
import re

from datetime import timedelta
from homeassistant.util import dt
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.const import (STATE_ON, STATE_OFF)
from homeassistant.util import Throttle
from homeassistant.components import (
    google)


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'calendar'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

DISCOVERY_PLATFORMS = {
    google.DISCOVER_CALENDARS: 'google',
}


def setup(hass, config):
    """Track states and offer events for calendars."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, 60, DISCOVERY_PLATFORMS)

    component.setup(config)

    return True

DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_OFFSET = '#-'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


# pylint: disable=too-many-instance-attributes
class CalendarEventDevice(Entity):
    """A calendar event device."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, calendar, data):
        """Create the Calendar Event Device.

        hass = HA instance
        calendar = reference for subclasses to get main cal object
        data = dict of track/search/name/offset
        """
        from homeassistant.helpers.entity import generate_entity_id
        self.hass = hass
        self._state = False
        self._calendar = calendar
        self._track = data.get('track', DEFAULT_CONF_TRACK_NEW)
        self._search = data.get('search', None)
        self._name = data.get('name')
        self._offset = data.get('offset', DEFAULT_CONF_OFFSET)
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT,
                                            self._name,
                                            hass=hass)
        self._start_listener = None
        self._end_listener = None

        self._cal_data = {
            'all_day': False,
            'offset_time': 0,
            'message': '',
            'start': None,
            'end': None,
            'location': None,
            'description': '',
        }

        if self._track:
            self.update()

    @property
    def offset_reached(self):
        """Have we reached the offset time specified in the event title."""
        if self._cal_data['offset_time'] > 0:
            start = self._cal_data['start']
            now = dt.now(start.tzinfo)
            offset = timedelta(minutes=self._cal_data['offset_time'])
            return now + offset >= start
        return False

    @property
    def state_attributes(self):
        """State Attributes for HA."""
        start = self._cal_data.get('start', None)
        end = self._cal_data.get('end', None)
        start = start.isoformat() if start is not None else None
        end = end.isoformat() if end is not None else None

        return {
            'message': self._cal_data.get('message', ''),
            'all_day': self._cal_data.get('all_day', False),
            'offset_reached': self.offset_reached,
            'start_time': start,
            'end_time': end,
            'location': self._cal_data.get('location', None),
            'description': self._cal_data.get('description', None),
        }

    @property
    def track(self):
        """Are we tracking events on this search sensor."""
        return self._track

    @property
    def is_all_day(self):
        """If the next event is all day then True."""
        return self._cal_data.get('all_day', False)

    @property
    def search(self):
        """Return the search string."""
        return self._search

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def is_on(self):
        """Return if the event in process."""
        return self._state

    @property
    def state(self):
        """Return the state of the calendar event."""
        return STATE_ON if self.is_on else STATE_OFF

    def cleanup(self):
        """Cleanup any start/end listeners that were setup."""
        from homeassistant.const import EVENT_TIME_CHANGED
        self._cal_data = {
            'all_day': False,
            'offset_time': 0,
            'message': '',
            'start': None,
            'end': None,
            'location': None,
            'description': None
        }

        if self._start_listener:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                          self._start_listener)
            self._start_listener = None
        if self._end_listener:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                          self._end_listener)
            self._end_listener = None

    def get_next_event(self):
        """Raise an error so that subclasses implement this."""
        raise NotImplementedError()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Search for the next event."""
        from homeassistant.const import EVENT_TIME_CHANGED
        from homeassistant.helpers.event import track_point_in_time

        event = self.get_next_event()
        if not event:
            self.cleanup()
            return

        def _get_date(date):
            """Get the dateTime from date or dateTime as a local."""
            if 'date' in date:
                return dt.as_local(dt.dt.datetime.combine(
                    dt.parse_date(date['date']), dt.dt.time()))
            else:
                return dt.parse_datetime(date['dateTime'])

        self._cal_data['all_day'] = 'date' in event['start']
        start = _get_date(event['start'])
        end = _get_date(event['end'])

        # check if the start/end times changed, if not then exit
        if start == self._cal_data['start'] and end == self._cal_data['end']:
            # don't redo the listener if we have the same start/end times
            return

        summary = event['summary']

        # check if we have an offset tag in the message
        search = re.search('{}([0-9]+)'.format(self._offset), summary)
        if search and search.group(1).isdigit():
            self._cal_data['offset_time'] = int(search.group(1))
            summary = summary[:search.start()] + summary[search.end():]
        else:
            self._cal_data['offset_time'] = 0  # default it

        # Remove the search term if we're using tags
        if self.search and self.search[0] == '#':
            summary = re.compile(re.escape(self.search),
                                 re.IGNORECASE).sub('', summary)

        # cleanup the string so we don't have a bunch of double+ spaces
        self._cal_data['message'] = re.sub('  +', '', summary).strip()

        self._cal_data['location'] = event.get('location', '')
        self._cal_data['description'] = event.get('description', '')
        self._cal_data['start'] = start
        self._cal_data['end'] = end

        if self._cal_data['start'] < dt.now():
            if not self.is_on:
                # trigger the device open
                self._state = True
        elif self._state:
            # we shouldn't be on right now
            self._state = False

        if not self._state:
            # schedule the device to open
            def _start(now):
                """What to do when the event start time is reached."""
                self._state = True
                self._start_listener = None
            if self._start_listener:
                self.hass.bus.remove_listener(
                    EVENT_TIME_CHANGED, self._start_listener)
            self._start_listener = track_point_in_time(self.hass,
                                                       _start,
                                                       self._cal_data['start'])

        # schedule the close
        def _end(now):
            """What to do when the event end time is reached."""
            self._state = False
            self.cleanup()
        self._end_listener = track_point_in_time(self.hass, _end,
                                                 self._cal_data['end'])

    def value_changed(self, state):
        """If the state changed then update_ha_state."""
        if self._state == state:
            self.update_ha_state()
