"""
Support for custom shell commands to retrieve values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.command_line/
"""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, DEVICE_CLASSES_SCHEMA, PLATFORM_SCHEMA)
from homeassistant.components.sensor.command_line import CommandSensorData
from homeassistant.const import (
    CONF_PAYLOAD_OFF, CONF_PAYLOAD_ON, CONF_NAME, CONF_VALUE_TEMPLATE,
    CONF_SENSOR_CLASS, CONF_COMMAND, CONF_DEVICE_CLASS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.deprecation import get_deprecated

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Binary Command Sensor'
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PAYLOAD_OFF, default=DEFAULT_PAYLOAD_OFF): cv.string,
    vol.Optional(CONF_PAYLOAD_ON, default=DEFAULT_PAYLOAD_ON): cv.string,
    vol.Optional(CONF_SENSOR_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Command line Binary Sensor."""
    name = config.get(CONF_NAME)
    command = config.get(CONF_COMMAND)
    payload_off = config.get(CONF_PAYLOAD_OFF)
    payload_on = config.get(CONF_PAYLOAD_ON)
    device_class = get_deprecated(config, CONF_DEVICE_CLASS, CONF_SENSOR_CLASS)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass
    data = CommandSensorData(command)

    add_devices([CommandBinarySensor(
        hass, data, name, device_class, payload_on, payload_off,
        value_template)])


class CommandBinarySensor(BinarySensorDevice):
    """Representation of a command line binary sensor."""

    def __init__(self, hass, data, name, device_class, payload_on,
                 payload_off, value_template):
        """Initialize the Command line binary sensor."""
        self._hass = hass
        self.data = data
        self._name = name
        self._device_class = device_class
        self._state = False
        self._payload_on = payload_on
        self._payload_off = payload_off
        self._value_template = value_template
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @ property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    def update(self):
        """Get the latest data and updates the state."""
        self.data.update()
        value = self.data.value

        if self._value_template is not None:
            value = self._value_template.render_with_possible_json_value(
                value, False)
        if value == self._payload_on:
            self._state = True
        elif value == self._payload_off:
            self._state = False
