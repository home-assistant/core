"""
Support for Blink system camera sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.blink/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.blink import (
    DOMAIN, DEFAULT_BRAND, DEFAULT_ATTRIBUTION)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS, ATTR_ATTRIBUTION, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['blink']

SENSOR_TYPES = {
    'temperature':
        ['Temperature', TEMP_FAHRENHEIT, 'mdi:thermometer'],
    'battery':
        ['Battery', '%', 'mdi:battery-80'],
    'motion_detected':
        ['Motion Detected', '', 'mdi:run-fast'],
    'wifi_strength':
        ['Wifi Signal', 'dBm', 'mdi:wifi-strength-2'],
    'status':
        ['Status', '', 'mdi:bell'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Blink sensor."""
    data = hass.data[DOMAIN]
    devs = list()
    for index, name in enumerate(data.blink.cameras):
        for sensor_type in SENSOR_TYPES:
            devs.append(BlinkSensor(name, sensor_type, index, data))

    add_entities(devs, True)


class BlinkSensor(Entity):
    """A Blink camera sensor."""

    def __init__(self, name, sensor_type, index, data):
        """Initialize sensors from Blink camera."""
        self._name = "{} {} {}".format(
            DOMAIN, name, SENSOR_TYPES[sensor_type][0])
        self._camera_name = name
        self._type = sensor_type
        self.data = data
        self.index = index
        self._camera = self.data.blink.cameras[name]
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]

    @property
    def name(self):
        """Return the name of the camera."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    @property
    def state(self):
        """Return the camera's current state."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Retrieve sensor data from the camera."""
        try:
            self._state = self._camera.attributes[self._type]
        except KeyError:
            self._state = None
            _LOGGER.error("%s not a valid camera attribute.  Did the blinkpy API change?", self._type)

    @property
    def device_state_attribution(self):
        """Return the device state attributes."""
        attr = {}
        attr[ATTR_ATTRIBUTION] = DEFAULT_ATTRIBUTION
        attr['brand'] = DEFAULT_BRAND
        return attr
