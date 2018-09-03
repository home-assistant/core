"""
Support for Eight Sleep binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.eight_sleep/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.eight_sleep import (
    DATA_EIGHT, EightSleepHeatEntity, CONF_BINARY_SENSORS, NAME_MAP)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['eight_sleep']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the eight sleep binary sensor."""
    if discovery_info is None:
        return

    name = 'Eight'
    sensors = discovery_info[CONF_BINARY_SENSORS]
    eight = hass.data[DATA_EIGHT]

    all_sensors = []

    for sensor in sensors:
        all_sensors.append(EightHeatSensor(name, eight, sensor))

    async_add_entities(all_sensors, True)


class EightHeatSensor(EightSleepHeatEntity, BinarySensorDevice):
    """Representation of a Eight Sleep heat-based sensor."""

    def __init__(self, name, eight, sensor):
        """Initialize the sensor."""
        super().__init__(eight)

        self._sensor = sensor
        self._mapped_name = NAME_MAP.get(self._sensor, self._sensor)
        self._name = '{} {}'.format(name, self._mapped_name)
        self._state = None

        self._side = self._sensor.split('_')[0]
        self._userid = self._eight.fetch_userid(self._side)
        self._usrobj = self._eight.users[self._userid]

        _LOGGER.debug("Presence Sensor: %s, Side: %s, User: %s",
                      self._sensor, self._side, self._userid)

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    async def async_update(self):
        """Retrieve latest state."""
        self._state = self._usrobj.bed_presence
