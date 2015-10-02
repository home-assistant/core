"""
homeassistant.components.sensor.command_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Allows to configure custom shell commands to turn a value for a sensor.

Configuration:

To use the command_line sensor you will need to add something like the
following to your configuration.yaml file.

sensor:
  platform: command_sensor
  name: "Command sensor"
  command: sensor_command
  unit_of_measurement: "°C"
  correction_factor: 0.0001
  decimal_places: 0

Variables:

name
*Optional
Name of the command sensor.

command
*Required
The action to take to get the value.

unit_of_measurement
*Optional
Defines the units of measurement of the sensor, if any.

correction_factor
*Optional
A float value to do some basic calculations.

decimal_places
*Optional
Number of decimal places of the value. Default is 0.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.command_sensor.html
"""
import logging
import subprocess
from datetime import timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Command Sensor"

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Add the Command Sensor. """

    if config.get('command') is None:
        _LOGGER.error('Missing required variable: "command"')
        return False

    data = CommandSensorData(config.get('command'))

    add_devices_callback([CommandSensor(
        data,
        config.get('name', DEFAULT_NAME),
        config.get('unit_of_measurement'),
        config.get('correction_factor', 1.0),
        config.get('decimal_places', 0)
    )])


# pylint: disable=too-many-arguments
class CommandSensor(Entity):
    """ Represents a sensor that is returning a value of a shell commands. """
    def __init__(self, data, name, unit_of_measurement, corr_factor,
                 decimal_places):
        self.data = data
        self._name = name
        self._state = False
        self._unit_of_measurement = unit_of_measurement
        self._corr_factor = float(corr_factor)
        self._decimal_places = decimal_places
        self.update()

    @property
    def name(self):
        """ The name of the sensor. """
        return self._name

    @property
    def unit_of_measurement(self):
        """ Unit the value is expressed in. """
        return self._unit_of_measurement

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    def update(self):
        """ Gets the latest data and updates the state. """
        self.data.update()
        value = self.data.value

        try:
            if value is not None:
                if self._corr_factor is not None:
                    self._state = round((float(value) * self._corr_factor),
                                        self._decimal_places)
                else:
                    self._state = value
        except ValueError:
            self._state = value


# pylint: disable=too-few-public-methods
class CommandSensorData(object):
    """ Class for handling the data retrieval. """

    def __init__(self, command):
        self.command = command
        self.value = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data with a shell command. """
        _LOGGER.info('Running command: %s', self.command)

        try:
            return_value = subprocess.check_output(self.command.split())
            self.value = return_value.strip().decode('utf-8')
        except subprocess.CalledProcessError:
            _LOGGER.error('Command failed: %s', self.command)
