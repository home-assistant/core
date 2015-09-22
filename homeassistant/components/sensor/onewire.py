""" Support for DS18B20 One Wire Sensors"""
from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELCIUS, TEMP_FAHRENHEIT
from glob import glob
import os
import time
import logging


BASE_DIR = '/sys/bus/w1/devices/'
DEVICE_FOLDERS = glob(os.path.join(BASE_DIR, '28*'))
SENSOR_IDS = []
DEVICE_FILES = []
for device_folder in DEVICE_FOLDERS:
    SENSOR_IDS.append(os.path.split(device_folder)[1])
    DEVICE_FILES.append(os.path.join(device_folder, 'w1_slave'))

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the one wire Sensors"""

    if DEVICE_FILES == []:
        _LOGGER.error('No onewire sensor found. Check if
                      dtoverlay=w1-gpio,gpiopin=4 is in your /boot/config.txt
                      and the correct gpiopin number is set.')
        return

    devs = []
    names = SENSOR_IDS

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
                names = [config['names'].get(sensor_id, sensor_id) for sensor_id in SENSOR_IDS]
    for device_file, name in zip(DEVICE_FILES, names):
        devs.append(OneWire(name, device_file, TEMP_CELCIUS))
    add_devices(devs)

    
class OneWire(Entity):
    """ A Dallas 1 Wire Sensor"""

    def __init__(self, name, device_file, unit_of_measurement):
        self._name = name
        self._device_file = device_file
        self._unit_of_measurement = unit_of_measurement

    def _read_temp_raw(self):
        """ read the temperature as it is returned by the sensor"""
        ds_device_file = open(self._device_file, 'r')
        lines = ds_device_file.readlines()
        ds_device_file.close()
        return lines

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        """ return temperature in unit_of_measurement"""
        lines = self._read_temp_raw()
        while lines[0].strip()[-3:] != 'YES':
            time.sleep(0.2)
            lines = self._read_temp_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temp = float(temp_string) / 1000.0
            if self._unit_of_measurement == TEMP_FAHRENHEIT:
                temp = temp * 9.0 / 5.0 + 32.0
            return temp

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
