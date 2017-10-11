"""
Demo platform that has two fake binary sensors.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
import asyncio
import logging


from datetime import timedelta


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

        for eni in range(0, 10):
            event = {
                'start': dt.now() + dt.dt.timedelta(days = eni),
                'end': dt.now() + dt.dt.timedelta(days = eni) + dt.dt.timedelta(minutes = 10 * eni),
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