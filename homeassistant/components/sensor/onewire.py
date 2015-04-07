""" Support for DS18B20 One Wire Sensors"""
from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELCIUS, TEMP_FAHRENHEIT
from glob import glob
import os
import time
import logging


BASE_DIR = '/sys/bus/w1/devices/'
DEVICE_FOLDERS = glob(os.path.join(BASE_DIR, '28*'))
SENSOR_IDS = [os.path.split(device_folder)[1] for device_folder in DEVICE_FOLDERS]
DEVICE_FILES = [os.path.join(device_folder, 'w1_slave') for device_folder in DEVICE_FOLDERS]

_LOGGER = logging.getLogger(__name__)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the one wire Sensors"""
    # TODO check if kernel modules are loaded

    # TODO implment config fore the name, but also default solution
    if DEVICE_FILES == []:
        _LOGGER.error('No onewire sensor found')
        return

    devs = []
    names = []
    try:
        ## only one name given
        if type(config['names']) == str:
            names = config[names]
        
        ## map names and sensors in given order
        elif type(config['names']) == list:
            names = config['names']

        ## map names with ids
        elif type(config['names']) == dict:
            for sensor_id in SENSOR_IDS:
                names.append(config['names'][sensor_id])
                
    except KeyError:
        ## use id as name
        if not config['names']:
            for sensor_id in SENSOR_IDS:
                names.append(sensor_id)
        
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
        f = open(self._device_file, 'r')
        lines = f.readlines()
        f.close()
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
            if self._unit_of_measurement ==  TEMP_FAHRENHEIT:
                temp = temp * 9.0 / 5.0 + 32.0
            return temp

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
    