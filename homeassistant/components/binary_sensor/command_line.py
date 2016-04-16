"""
Support for custom shell commands to to retrieve values.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.command/
"""
import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sensor.command_line import CommandSensorData
from homeassistant.const import CONF_VALUE_TEMPLATE
from homeassistant.helpers import template

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Binary Command Sensor"
DEFAULT_PAYLOAD_ON = 'ON'
DEFAULT_PAYLOAD_OFF = 'OFF'

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Command Sensor."""
    if config.get('command') is None:
        _LOGGER.error('Missing required variable: "command"')
        return False

    data = CommandSensorData(config.get('command'))

    add_devices([CommandBinarySensor(
        hass,
        data,
        config.get('name', DEFAULT_NAME),
        config.get('payload_on', DEFAULT_PAYLOAD_ON),
        config.get('payload_off', DEFAULT_PAYLOAD_OFF),
        config.get(CONF_VALUE_TEMPLATE)
    )])


# pylint: disable=too-many-arguments
class CommandBinarySensor(BinarySensorDevice):
    """Represent a command line binary sensor."""

    def __init__(self, hass, data, name, payload_on,
                 payload_off, value_template):
        """Initialize the Command line binary sensor."""
        self._hass = hass
        self.data = data
        self._name = name
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

    def update(self):
        """Get the latest data and updates the state."""
        self.data.update()
        value = self.data.value

        if self._value_template is not None:
            value = template.render_with_possible_json_value(
                self._hass, self._value_template, value, False)
        if value == self._payload_on:
            self._state = True
        elif value == self._payload_off:
            self._state = False
