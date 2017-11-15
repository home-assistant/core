"""
Demo platform that has two fake binary sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import asyncio
import logging


from datetime import timedelta
from random import randint, randrange, choice

from homeassistant.util import dt
from homeassistant.components.calendar import Calendar, CalendarEvent

_LOGGER = logging.getLogger(__name__)

DOMAIN = "DemoCalendar"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Demo Calendar platform."""
    add_devices([
        DemoCalendar(hass, 'DemoCalendar1'),
        DemoCalendar(hass, 'DemoCalendar2')
    ])


class DemoCalendar(Calendar):
    """Demo Calendar entity."""

    def __init__(self, hass, name):
        """Initialize Demo Calender entity."""
        self._events = []
        self._name = name
        self._next_event = None

        events = [
            'Football',
            'Doctor',
            'Meeting with Jim',
            'Open house',
            'Shopping',
            'Cleaning lady'
        ]

        today = dt.now()

        for eni in range(0, 10):
            start = today.replace(day=randint(1, 30),
                                  hour=randint(6, 19),
                                  minute=randrange(0, 60, 15))
            end = start + dt.dt.timedelta(days=randint(0, 3),
                                          hours=randint(1, 6),
                                          minutes=randrange(0, 60, 15))

            event = DemoCalendarEvent(start, end, choice(events))
            self._events.append(event)

        # Ensure always 1 event is active during creation of calendar 1
        if name == 'DemoCalendar1':
            event = DemoCalendarEvent(dt.now() - dt.dt.timedelta(hours=1),
                                      dt.now() + dt.dt.timedelta(hours=2),
                                      'Programming')
            self._events.append(event)

        self._events.sort(key=lambda event: event.start)

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
        """Calendar events."""
        return self._events

    @asyncio.coroutine
    def async_update(self):
        """Update calendar events."""
        _LOGGER.debug('Updating demo calendar')


class DemoCalendarEvent(CalendarEvent):
    """class for creating demo events."""

    def __init__(self, start, end, message):
        """Initialize google event."""
        self._start = start
        self._end = end
        self._message = message
