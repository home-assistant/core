"""
Support for showing the time in a different time zone.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.worldclock/
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = "Worldclock Sensor"
ICON = 'mdi:clock'
TIME_STR_FORMAT = "%H:%M"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Worldclock sensor."""
    try:
        time_zone = dt_util.get_time_zone(config.get('time_zone'))
    except AttributeError:
        _LOGGER.error("time_zone in platform configuration is missing.")
        return False

    if time_zone is None:
        _LOGGER.error("Timezone '%s' is not valid.", config.get('time_zone'))
        return False

    add_devices([WorldClockSensor(
        time_zone,
        config.get('name', DEFAULT_NAME)
    )])


class WorldClockSensor(Entity):
    """Represenatation of a Worldclock sensor."""

    def __init__(self, time_zone, name):
        """Initialize the sensor."""
        self._name = name
        self._time_zone = time_zone
        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the time and updates the states."""
        self._state = dt_util.now(time_zone=self._time_zone).strftime(
            TIME_STR_FORMAT)
