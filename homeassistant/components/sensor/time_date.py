"""
Support for showing the date and the time.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.time_date/
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
OPTION_TYPES = {
    'time': 'Time',
    'date': 'Date',
    'date_time': 'Date & Time',
    'time_date': 'Time & Date',
    'beat': 'Time (beat)',
    'time_utc': 'Time (UTC)',
}

TIME_STR_FORMAT = "%H:%M"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Time and Date sensor."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant config")
        return False

    dev = []
    for variable in config['display_options']:
        if variable not in OPTION_TYPES:
            _LOGGER.error('Option type: "%s" does not exist', variable)
        else:
            dev.append(TimeDateSensor(variable))

    add_devices(dev)


# pylint: disable=too-few-public-methods
class TimeDateSensor(Entity):
    """Implementation of a Time and Date sensor."""

    def __init__(self, option_type):
        """Initialize the sensor."""
        self._name = OPTION_TYPES[option_type]
        self.type = option_type
        self._state = None
        self.update()

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
        if "date" in self.type and "time" in self.type:
            return "mdi:calendar-clock"
        elif "date" in self.type:
            return "mdi:calendar"
        else:
            return "mdi:clock"

    def update(self):
        """Get the latest data and updates the states."""
        time_date = dt_util.utcnow()
        time = dt_util.as_local(time_date).strftime(TIME_STR_FORMAT)
        time_utc = time_date.strftime(TIME_STR_FORMAT)
        date = dt_util.as_local(time_date).date().isoformat()

        # Calculate the beat (Swatch Internet Time) time without date.
        hours, minutes, seconds = time_date.strftime('%H:%M:%S').split(':')
        beat = ((int(seconds) + (int(minutes) * 60) + ((int(hours) + 1) *
                                                       3600)) / 86.4)

        if self.type == 'time':
            self._state = time
        elif self.type == 'date':
            self._state = date
        elif self.type == 'date_time':
            self._state = date + ', ' + time
        elif self.type == 'time_date':
            self._state = time + ', ' + date
        elif self.type == 'time_utc':
            self._state = time_utc
        elif self.type == 'beat':
            self._state = '{0:.2f}'.format(beat)
