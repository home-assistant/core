"""
The Habitica sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.habitica/
"""

import logging
from datetime import timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components import habitica

_LOGGER = logging.getLogger(__name__)
SENSOR_DATA_IDX = 'sensor.' + habitica.DOMAIN
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the habitica platform."""
    if discovery_info is None:
        return

    name = discovery_info[habitica.CONF_NAME]
    sensors = discovery_info[habitica.CONF_SENSORS]
    if not sensors:
        sensors = habitica.ALL_SENSORS_TYPES
    sensor_data = hass.data.get(SENSOR_DATA_IDX, {})
    sensor_data[name] = HabitipyData(hass, name)
    hass.data[SENSOR_DATA_IDX] = sensor_data
    await sensor_data[name]()
    async_add_devices([
        HabitipySensor(name, sensor)
        for sensor in sensors
    ], True)
    return True


class HabitipyData:
    """Habitica API user data cache."""

    def __init__(self, hass, name):
        """
        Habitica API user data cache.

        hass - hass object
        name - habitica platform name
        """
        self.hass = hass
        self.name = name
        self.data = None

    def __call__(self):
        """Return update async functions."""
        return self._update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def _update(self):
        api = self.hass.data[habitica.DOMAIN][self.name]
        self.data = await api.user.get()


class HabitipySensor(Entity):
    """A generic Habitica sensor."""

    def __init__(self, name, sensor_name):
        """
        A generic Habitica sensor.

        name - Habitica platform name
        sensor_name - one of the names from ALL_SENSOR_TYPES
        """
        self._name = name
        self._sensor_name = sensor_name
        self._sensor_type = habitica.SENSORS_TYPES[sensor_name]
        self._state = None

    async def async_update(self):
        """Update Condition and Forecast."""
        updater = self.hass.data[SENSOR_DATA_IDX][self._name]
        await updater()
        data = updater.data
        for element in self._sensor_type.path:
            data = data[element]
        self._state = data

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._sensor_type.icon

    @property
    def name(self):
        """Return the name of the sensor."""
        return "_".join((habitica.DOMAIN, self._name, self._sensor_name))

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor_type.unit
