"""
Allows to configure custom shell commands to turn a value for a sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.command_line/
"""
import logging
import subprocess
from datetime import timedelta

from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import template
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Command Sensor"

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the Command Sensor."""
    if config.get('command') is None:
        _LOGGER.error('Missing required variable: "command"')
        return False

    data = CommandSensorData(config.get('command'))

    add_devices_callback([CommandSensor(
        hass,
        data,
        config.get('name', DEFAULT_NAME),
        config.get('unit_of_measurement'),
        config.get(CONF_VALUE_TEMPLATE)
    )])


# pylint: disable=too-many-arguments
class CommandSensor(Entity):
    """Representation of a sensor that is using shell commands."""

    def __init__(self, hass, data, name, unit_of_measurement, value_template):
        """Initialize the sensor."""
        self._hass = hass
        self.data = data
        self._name = name
        self._state = False
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

        if self._value_template is not None:
            self._state = template.render_with_possible_json_value(
                self._hass, self._value_template, value, 'N/A')
        else:
            self._state = value


# pylint: disable=too-few-public-methods
class CommandSensorData(object):
    """The class for handling the data retrieval."""

    def __init__(self, command):
        """Initialize the data object."""
        self.command = command
        self.value = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data with a shell command."""
        _LOGGER.info('Running command: %s', self.command)

        try:
            return_value = subprocess.check_output(self.command, shell=True)
            self.value = return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error('Command failed: %s', self.command)
