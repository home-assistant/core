"""
Demo platform that has two fake binary sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import asyncio
import logging


from datetime import timedelta
from random import randint, randrange

from homeassistant.util import Throttle


import homeassistant.util.dt as dt
from homeassistant.components.calendar import Calendar

_LOGGER = logging.getLogger(__name__)
DOMAIN = "DemoCalendar"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

@asyncio.coroutine
def async_get_handler(hass, config, discovery_info=None):
    return DemoCalendar(hass, DOMAIN)

class DemoCalendar(Calendar):
    def __init__(self, hass, name):
        self._events = []

        test = "Lorem Ipsum"

        today = dt.now()

        for eni in range(0, 10):
            start = today.replace(day=randint(1, 30), hour=randint(6, 19), minute=randrange(0, 60, 15))
            end = start + dt.dt.timedelta(days=randint(0, 3), hours=randint(1, 6), minutes=randrange(0, 60, 15))

            event = {
                'start': start,
                'end': end,
                'text': test
            }
            self._events.append(event)

        super().__init__(hass, name)

    @asyncio.coroutine
    def async_get_events(self):
        return self._events

    @asyncio.coroutine
    def async_update(self):
        _LOGGER.info('Updating demo calendar')