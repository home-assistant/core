"""
Demo platform that has two fake binary sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import asyncio
import logging


from datetime import timedelta
from random import randint, randrange, choice

from homeassistant.util import Throttle


import homeassistant.util.dt as dt
from homeassistant.components.calendar import Calendar

_LOGGER = logging.getLogger(__name__)
DOMAIN = "DemoCalendar"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


@asyncio.coroutine
def async_get_handler(hass, config, discovery_info=None):
    """Setup demo calendar platform."""
    calendars = []

    calendars.append(DemoCalendar(hass, 'DemoCalendar1'))
    calendars.append(DemoCalendar(hass, 'DemoCalendar2'))

    return calendars


class DemoCalendar(Calendar):
    """Demo Calendar entity."""

    def __init__(self, hass, name):
        """Initialize Demo Calender entity."""
        self._events = []

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

            event = {
                'start': start,
                'end': end,
                'text': choice(events)
            }
            self._events.append(event)

        super().__init__(hass, name)

    @asyncio.coroutine
    def async_get_events(self):
        """Calendar events."""
        return self._events

    @asyncio.coroutine
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def async_update(self):
        """Update calendar events."""
        _LOGGER.info('Updating demo calendar')
