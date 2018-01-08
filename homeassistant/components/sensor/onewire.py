"""
Support for 1-Wire environment sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.onewire/
"""
import os
import time
import logging
from glob import glob

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.sensor import PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)

CONF_MOUNT_DIR = 'mount_dir'
CONF_NAMES = 'names'

DEFAULT_MOUNT_DIR = '/sys/bus/w1/devices/'
DEVICE_SENSORS = {'10': {'temperature': 'temperature'},
                  '12': {'temperature': 'TAI8570/temperature',
                         'pressure': 'TAI8570/pressure'},
                  '22': {'temperature': 'temperature'},
                  '26': {'temperature': 'temperature',
                         'humidity': 'humidity',
                         'pressure': 'B1-R1-A/pressure'},
                  '28': {'temperature': 'temperature'},
                  '3B': {'temperature': 'temperature'},
                  '42': {'temperature': 'temperature'}}

SENSOR_TYPES = {
    'temperature': ['temperature', TEMP_CELSIUS],
    'humidity': ['humidity', '%'],
    'pressure': ['pressure', 'mb'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAMES): {cv.string: cv.string},
    vol.Optional(CONF_MOUNT_DIR, default=DEFAULT_MOUNT_DIR): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the one wire Sensors."""
    base_dir = config.get(CONF_MOUNT_DIR)
    devs = []
    device_names = {}
    if 'names' in config:
        if isinstance(config['names'], dict):
            device_names = config['names']

    if base_dir == DEFAULT_MOUNT_DIR:
        for device_family in DEVICE_SENSORS:
            for device_folder in glob(os.path.join(base_dir, device_family +
                                                   '[.-]*')):
                sensor_id = os.path.split(device_folder)[1]
                device_file = os.path.join(device_folder, 'w1_slave')
                devs.append(OneWireDirect(device_names.get(sensor_id,
                                                           sensor_id),
                                          device_file, 'temperature'))
    else:
        for family_file_path in glob(os.path.join(base_dir, '*', 'family')):
            family_file = open(family_file_path, "r")
            family = family_file.read()
            if family in DEVICE_SENSORS:
                for sensor_key, sensor_value in DEVICE_SENSORS[family].items():
                    sensor_id = os.path.split(
                        os.path.split(family_file_path)[0])[1]
                    device_file = os.path.join(
                        os.path.split(family_file_path)[0], sensor_value)
                    devs.append(OneWireOWFS(device_names.get(sensor_id,
                                                             sensor_id),
                                            device_file, sensor_key))

    if devs == []:
        _LOGGER.error("No onewire sensor found. Check if dtoverlay=w1-gpio "
                      "is in your /boot/config.txt. "
                      "Check the mount_dir parameter if it's defined")
        return

    add_devices(devs, True)


class OneWire(Entity):
    """Implementation of an One wire Sensor."""

    def __init__(self, name, device_file, sensor_type):
        """Initialize the sensor."""
        self._name = name+' '+sensor_type.capitalize()
        self._device_file = device_file
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._state = None

    def _read_value_raw(self):
        """Read the value as it is returned by the sensor."""
        with open(self._device_file, 'r') as ds_device_file:
            lines = ds_device_file.readlines()
        return lines

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement


class OneWireDirect(OneWire):
    """Implementation of an One wire Sensor directly connected to RPI GPIO."""

    def update(self):
        """Get the latest data from the device."""
        value = None
        lines = self._read_value_raw()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = self._read_value_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            value_string = lines[1][equals_pos + 2:]
            value = round(float(value_string) / 1000.0, 1)
        self._state = value


class OneWireOWFS(OneWire):
    """Implementation of an One wire Sensor through owfs."""

    def update(self):
        """Get the latest data from the device."""
        value = None
        try:
            value_read = self._read_value_raw()
            if len(value_read) == 1:
                value = round(float(value_read[0]), 1)
        except ValueError:
            _LOGGER.warning("Invalid value read from %s", self._device_file)
        except FileNotFoundError:
            _LOGGER.warning("Cannot read from sensor: %s", self._device_file)

        self._state = value
