"""
Allows to configure custom shell commands to turn a value for a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.command_line/
"""
import logging
import subprocess
import shlex

from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers import template
from homeassistant.exceptions import TemplateError
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, CONF_UNIT_OF_MEASUREMENT, CONF_COMMAND,
    STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Command Sensor'

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Command Sensor."""
    name = config.get(CONF_NAME)
    command = config.get(CONF_COMMAND)
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass
    data = CommandSensorData(hass, command)

    add_devices([CommandSensor(hass, data, name, unit, value_template)], True)


class CommandSensor(Entity):
    """Representation of a sensor that is using shell commands."""

    def __init__(self, hass, data, name, unit_of_measurement, value_template):
        """Initialize the sensor."""
        self._hass = hass
        self.data = data
        self._name = name
        self._state = None
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template

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

    def __init__(self, hass, command):
        """Initialize the data object."""
        self.value = None
        self.hass = hass
        self.command = command

    def update(self):
        """Get the latest data with a shell command."""
        command = self.command
        cache = {}

        if command in cache:
            prog, args, args_compiled = cache[command]
        elif ' ' not in command:
            prog = command
            args = None
            args_compiled = None
            cache[command] = (prog, args, args_compiled)
        else:
            prog, args = command.split(' ', 1)
            args_compiled = template.Template(args, self.hass)
            cache[command] = (prog, args, args_compiled)

        if args_compiled:
            try:
                args_to_render = {"arguments": args}
                rendered_args = args_compiled.render(args_to_render)
            except TemplateError as ex:
                _LOGGER.exception("Error rendering command template: %s", ex)
                return
        else:
            rendered_args = None

        if rendered_args == args:
            # No template used. default behavior
            shell = True
        else:
            # Template used. Construct the string used in the shell
            command = str(' '.join([prog] + shlex.split(rendered_args)))
            shell = True
        try:
            _LOGGER.info("Running command: %s", command)
            return_value = subprocess.check_output(
                command, shell=shell, timeout=15)
            self.value = return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error("Command failed: %s", command)
        except subprocess.TimeoutExpired:
            _LOGGER.error("Timeout for command: %s", command)
