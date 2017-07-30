"""
Allows to configure custom shell commands to turn a value for a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.command_line/
"""
from datetime import timedelta
import logging
import subprocess

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, CONF_UNIT_OF_MEASUREMENT, CONF_COMMAND,
    STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Command Sensor'

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Command Sensor."""
    name = config.get(CONF_NAME)
    command = config.get(CONF_COMMAND)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass
    data = CommandSensorData(command)

    add_devices([CommandSensor(hass, data, name, unit, value_template)])


class CommandSensor(Entity):
    """Representation of a sensor that is using shell commands."""

    def __init__(self, hass, data, name, unit_of_measurement, value_template):
        """Initialize the sensor."""
        self._hass = hass
        self.data = data
        self._name = name
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        self.data.update()
        value = self.data.value

        if value is None:
            value = STATE_UNKNOWN
        elif self._value_template is not None:
            self._state = self._value_template.render_with_possible_json_value(
                value, STATE_UNKNOWN)
        else:
            self._state = value


class CommandSensorData(object):
    """The class for handling the data retrieval."""

    def __init__(self, command):
        """Initialize the data object."""
        self.command = command
        self.value = None

    def update(self):
        """Get the latest data with a shell command."""
        _LOGGER.info("Running command: %s", self.command)

        try:
            return_value = subprocess.check_output(
                self.command, shell=True, timeout=15)
            self.value = return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error("Command failed: %s", self.command)
        except subprocess.TimeoutExpired:
            _LOGGER.error("Timeout for command: %s", self.command)
