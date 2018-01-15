"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.rainbird/
"""
import logging

import voluptuous as vol

from homeassistant.components.rainbird import DATA_RAINBIRD
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['rainbird']

_LOGGER = logging.getLogger(__name__)

# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    'rainsensor': ['Rainsensor', None, 'mdi:water']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a Rain Bird sensor."""
    controller = hass.data[DATA_RAINBIRD]

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        sensors.append(
            RainBirdSensor(controller, sensor_type))

    add_devices(sensors, True)


class RainBirdSensor(Entity):
    """A sensor implementation for Rain Bird device."""

    def __init__(self, controller, sensor_type):
        """Initialize the Rain Bird sensor."""
        self._sensor_type = sensor_type
        self._controller = controller
        self._name = SENSOR_TYPES[self._sensor_type][0]
        self._icon = SENSOR_TYPES[self._sensor_type][2]
        self._unit_of_measurement = SENSOR_TYPES[self._sensor_type][1]
        self._state = None

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        if self._sensor_type == 'rainsensor':
            self._state = self._controller.currentRainSensorState()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return icon."""
        return self._icon
