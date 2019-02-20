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
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


async def async_setup_platform(
        hass, config, async_add_devices, discovery_info=None):
    """Set up the habitica platform."""
    if discovery_info is None:
        return

    name = discovery_info[habitica.CONF_NAME]
    sensors = discovery_info[habitica.CONF_SENSORS]
    sensor_data = HabitipyData(hass.data[habitica.DOMAIN][name])
    await sensor_data.update()
    async_add_devices([
        HabitipySensor(name, sensor, sensor_data)
        for sensor in sensors
    ], True)


class HabitipyData:
    """Habitica API user data cache."""

    def __init__(self, api):
        """
        Habitica API user data cache.

        api - HAHabitipyAsync object
        """
        self.api = api
        self.data = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self):
        """Get a new fix from Habitica servers."""
        self.data = await self.api.user.get()


class HabitipySensor(Entity):
    """A generic Habitica sensor."""

    def __init__(self, name, sensor_name, updater):
        """
        Init a generic Habitica sensor.

        name - Habitica platform name
        sensor_name - one of the names from ALL_SENSOR_TYPES
        """
        self._name = name
        self._sensor_name = sensor_name
        self._sensor_type = habitica.SENSORS_TYPES[sensor_name]
        self._state = None
        self._updater = updater

    async def async_update(self):
        """Update Condition and Forecast."""
        await self._updater.update()
        data = self._updater.data
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
        return "{0}_{1}_{2}".format(
            habitica.DOMAIN, self._name, self._sensor_name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor_type.unit
