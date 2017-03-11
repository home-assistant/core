"""
Support for showing the date and the time.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.time_date/
"""
from datetime import timedelta
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DISPLAY_OPTIONS
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

TIME_STR_FORMAT = '%H:%M'

OPTION_TYPES = {
    'time': 'Time',
    'date': 'Date',
    'date_time': 'Date & Time',
    'time_date': 'Time & Date',
    'beat': 'Internet Time',
    'time_utc': 'Time (UTC)',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DISPLAY_OPTIONS, default=['time']):
        vol.All(cv.ensure_list, [vol.In(OPTION_TYPES)]),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Time and Date sensor."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")
        return False

    devices = []
    for variable in config[CONF_DISPLAY_OPTIONS]:
        devices.append(TimeDateSensor(variable))

    async_add_devices(devices, True)
    return True


class TimeDateSensor(Entity):
    """Implementation of a Time and Date sensor."""

    def __init__(self, option_type):
        """Initialize the sensor."""
        self._name = OPTION_TYPES[option_type]
        self.type = option_type
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if 'date' in self.type and 'time' in self.type:
            return 'mdi:calendar-clock'
        elif 'date' in self.type:
            return 'mdi:calendar'
        else:
            return 'mdi:clock'

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data and updates the states."""
        time_date = dt_util.utcnow()
        time = dt_util.as_local(time_date).strftime(TIME_STR_FORMAT)
        time_utc = time_date.strftime(TIME_STR_FORMAT)
        date = dt_util.as_local(time_date).date().isoformat()

        # Calculate Swatch Internet Time.
        time_bmt = time_date + timedelta(hours=1)
        delta = timedelta(
            hours=time_bmt.hour, minutes=time_bmt.minute,
            seconds=time_bmt.second, microseconds=time_bmt.microsecond)
        beat = int((delta.seconds + delta.microseconds / 1000000.0) / 86.4)

        if self.type == 'time':
            self._state = time
        elif self.type == 'date':
            self._state = date
        elif self.type == 'date_time':
            self._state = '{}, {}'.format(date, time)
        elif self.type == 'time_date':
            self._state = '{}, {}'.format(time, date)
        elif self.type == 'time_utc':
            self._state = time_utc
        elif self.type == 'beat':
            self._state = '@{0:03d}'.format(beat)
