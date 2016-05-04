"""
Support for custom shell commands to to retrieve values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.command/
"""
# pylint: disable=import-error
import logging
from datetime import timedelta
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.util import Throttle


_LOGGER = logging.getLogger(__name__)

DOMAIN = 'google_calendar'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_NAME = 'name'
CONF_TRACK = 'track'
CONF_SEARCH = 'search'
CONF_OFFSET = 'offset'

DEFAULT_CONF_TRACK_NEW = True
DEFAULT_CONF_OFFSET = '#-'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Z-Wave platform for sensors."""
    if discovery_info is None:
        return

    add_devices([GoogleCalendarSensor(hass, discovery_info['cal_id'], data)
                 for data in discovery_info['entities'] if data['track']])


# pylint: disable=too-many-instance-attributes
class GoogleCalendarSensor(BinarySensorDevice):
    """A calendar binary sensor.

    It enables/disabled based on:
     - Search criteria
     - all events on a Google calendar.

    """

    # pylint: disable=too-many-arguments
    def __init__(self, hass, calendar_id, data):
        """Create the Google Calendar Sensor."""
        from homeassistant.helpers.entity import generate_entity_id
        self.hass = hass
        self._calendar_id = calendar_id
        self._track = data.get('track', DEFAULT_CONF_TRACK_NEW)
        self._search = data.get('search', None)
        self._name = data.get('name')
        self._all_day = False
        self._state = False
        self._offset = data.get('offset', DEFAULT_CONF_OFFSET)
        self._offset_time = 0
        self.entity_id = generate_entity_id(ENTITY_ID_FORMAT,
                                            self._name,
                                            hass=hass)

        self._message = ""
        self._start = None
        self._end = None
        self._start_listener = None
        self._end_listener = None

        if self._track:
            self.update()

    @property
    def time_till(self):
        """Return minutes until the event starts."""
        from homeassistant.util import dt
        if self._start and self._start > dt.now():
            return round((self._start - dt.now()).total_seconds()/60)
        return 0

    @property
    def offset(self):
        """Have we reached the offset time specified in the event title."""
        if self._offset_time > 0:
            return self._offset_time >= self.time_till
        return False

    @property
    def state_attributes(self):
        """State Attributes for HA."""
        return {
            'message': self._message or '',
            'all_day': self.is_all_day,
            'time_till': self.time_till,
            'offset': self.offset,
        }

    @property
    def track(self):
        """Are we tracking events on this search sensor."""
        return self._track

    @property
    def is_all_day(self):
        """If the next event is all day then True."""
        return self._all_day

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

    def cleanup(self):
        """Cleanup any start/end listeners that were setup."""
        from homeassistant.const import EVENT_TIME_CHANGED
        self._start = self._end = self._message = None
        if self._start_listener:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                          self._start_listener)
            self._start_listener = None
        if self._end_listener:
            self.hass.bus.remove_listener(EVENT_TIME_CHANGED,
                                          self._end_listener)
            self._end_listener = None
        self._offset_time = 0

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Search for the next event."""
        from homeassistant.util import dt
        from homeassistant.const import EVENT_TIME_CHANGED
        from homeassistant.helpers.event import track_point_in_time
        from homeassistant.components.google_calendar import get_next_event
        event = get_next_event(self.hass, self._calendar_id, self.search)
        if not event:
            # We have no event so lets cleanup if we need and exit.
            self.cleanup()
            return

        def _get_date(date):
            """Get the dateTime from date or dateTime as a local."""
            if 'date' in date:
                return dt.as_local(dt.dt.datetime.combine(
                    dt.parse_date(date['date']), dt.dt.time()))
            else:
                return dt.parse_datetime(date['dateTime'])

        self._all_day = 'date' in event['start']
        start = _get_date(event['start'])
        end = _get_date(event['end'])

        # check if the start/end times changed, if not then exit
        if start == self._start and end == self._end:
            # don't redo the listener if we have the same start/end times
            _LOGGER.info('There were no changes')
            return

        summary = event['summary']

        # check if we have an offset tag in the message
        import re
        search = re.search('{}([0-9]+)'.format(self._offset), summary)
        if search and search.group(1).isdigit():
            self._offset_time = int(search.group(1))
            summary = summary[:search.start()] + summary[search.end():]
        else:
            self._offset_time = 0  # default it

        # Remove the search term if we're using tags
        if self.search and self.search[0] == '#':
            summary = re.compile(re.escape(self.search),
                                 re.IGNORECASE).sub('', summary)

        # cleanup the string so we don't have a bunch of double+ spaces
        self._message = re.sub('  +', '', summary).strip()

        self._start = start
        self._end = end

        if self._start < dt.now():
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
                                                       self._start)

        # schedule the close
        def _end(now):
            """What to do when the event end time is reached."""
            self._state = False
            self.cleanup()
        self._end_listener = track_point_in_time(self.hass, _end, self._end)

    def value_changed(self, state):
        """If the state changed then update_ha_state."""
        if self._state == state:
            self.update_ha_state()
