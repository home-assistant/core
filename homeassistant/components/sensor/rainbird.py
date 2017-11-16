"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.rainbird import (
    DATA_RAINBIRD)
#from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_MONITORED_CONDITIONS

DEPENDENCIES = ['rainbird']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSORS)):
        vol.All(cv.ensure_list, [vol.In(SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a raincloud device."""
    controller = hass.data[DATA_RAINBIRD]

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        if sensor_type == 'rainsensor':
            sensors.append(
                RainBirdSensor(controller, sensor_type))

    add_devices(sensors, True)
    return True


class RainBirdSensor(Entity):
    """A sensor implementation for rain bird device."""

    def __init__(self, controller, sensor_type):
        """Initialize rain bird sensor."""
        self._sensor_type = sensor_type
        self._controller = controller

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating RainBird sensor: %s", self._name)
        if self._sensor_type == 'rainsensor':
            self._state = self._controller.currentRainSensorState()

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._sensor_type == 'rainsensor':
            return 'mdi:water'
