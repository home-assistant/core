"""
Support for Rain Bird Irrigation system LNK WiFi Module.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/rainbird/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['rainbird']
DATA_RAINBIRD = 'rainbird'
_LOGGER = logging.getLogger(__name__)

# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    'rainsensor': ['Rainsensor', None, 'water']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
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
        self._name = SENSOR_TYPES.get(self._sensor_type)[0]
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[2])
        self._state = None

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
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[1]

    @property
    def icon(self):
        """Icon to use in the frontend."""
        if self._sensor_type == 'rainsensor':
            return 'mdi:water'
