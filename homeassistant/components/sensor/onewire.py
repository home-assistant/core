"""
Support for 1-Wire temperature sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.onewire/
"""
import os
import time
import logging
from glob import glob
import voluptuous as vol
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import STATE_UNKNOWN, TEMP_CELSIUS
from homeassistant.components.sensor import PLATFORM_SCHEMA

CONF_MOUNT_DIR = 'mount_dir'
CONF_NAMES = 'names'
DEFAULT_MOUNT_DIR = '/sys/bus/w1/devices/'
DEVICE_FAMILIES = ('10', '22', '28', '3B', '42')

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAMES): {cv.string: cv.string},
    vol.Optional(CONF_MOUNT_DIR, default=DEFAULT_MOUNT_DIR): cv.string,
})

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the one wire Sensors."""
    base_dir = config.get(CONF_MOUNT_DIR)
    sensor_ids = []
    device_files = []
    for device_family in DEVICE_FAMILIES:
        for device_folder in glob(os.path.join(base_dir, device_family +
                                               '[.-]*')):
            sensor_ids.append(os.path.split(device_folder)[1])
            if base_dir == DEFAULT_MOUNT_DIR:
                device_files.append(os.path.join(device_folder, 'w1_slave'))
            else:
                device_files.append(os.path.join(device_folder, 'temperature'))

    if device_files == []:
        _LOGGER.error('No onewire sensor found. Check if '
                      'dtoverlay=w1-gpio is in your /boot/config.txt. '
                      'Check the mount_dir parameter if it\'s defined.')
        return

    devs = []
    names = sensor_ids

    for key in config.keys():
        if key == "names":
            # only one name given
            if isinstance(config['names'], str):
                names = [config['names']]
            # map names and sensors in given order
            elif isinstance(config['names'], list):
                names = config['names']
            # map names to ids.
            elif isinstance(config['names'], dict):
                names = []
                for sensor_id in sensor_ids:
                    names.append(config['names'].get(sensor_id, sensor_id))
    for device_file, name in zip(device_files, names):
        devs.append(OneWire(name, device_file))
    add_devices(devs)


class OneWire(Entity):
    """Implementation of an One wire Sensor."""

    def __init__(self, name, device_file):
        """Initialize the sensor."""
        self._name = name
        self._device_file = device_file
        self._state = STATE_UNKNOWN
        self.update()

    def _read_temp_raw(self):
        """Read the temperature as it is returned by the sensor."""
        ds_device_file = open(self._device_file, 'r')
        lines = ds_device_file.readlines()
        ds_device_file.close()
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
        return TEMP_CELSIUS

    def update(self):
        """Get the latest data from the device."""
        temp = -99
        if self._device_file.startswith(DEFAULT_MOUNT_DIR):
            lines = self._read_temp_raw()
            while lines[0].strip()[-3:] != 'YES':
                time.sleep(0.2)
                lines = self._read_temp_raw()
            equals_pos = lines[1].find('t=')
            if equals_pos != -1:
                temp_string = lines[1][equals_pos+2:]
                temp = round(float(temp_string) / 1000.0, 1)
        else:
            try:
                ds_device_file = open(self._device_file, 'r')
                temp_read = ds_device_file.readlines()
                ds_device_file.close()
                if len(temp_read) == 1:
                    temp = round(float(temp_read[0]), 1)
            except ValueError:
                _LOGGER.warning('Invalid temperature value read from ' +
                                self._device_file)
            except FileNotFoundError:
                _LOGGER.warning('Cannot read from sensor: ' +
                                self._device_file)

        if temp < -55 or temp > 125:
            return
        self._state = temp
