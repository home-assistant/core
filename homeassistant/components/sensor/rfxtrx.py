"""
homeassistant.components.sensor.rfxtrx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shows sensor values from rfxtrx sensors.

Possible config keys:
device="path to rfxtrx device"

Example:

sensor 2:
 platform: rfxtrx
 device :  /dev/serial/by-id/usb-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0

"""
import logging
from collections import OrderedDict

from homeassistant.const import (TEMP_CELCIUS)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['https://github.com/Danielhiversen/pyRFXtrx/archive/master.zip'
                '#RFXtrx>=0.15']

DATA_TYPES = OrderedDict([
    ('Temperature', TEMP_CELCIUS),
    ('Humidity', '%'),
    ('Forecast', ''),
    ('Barometer', ''),
    ('Wind direction', ''),
    ('Humidity status', ''),
    ('Humidity status numeric', ''),
    ('Forecast numeric', ''),
    ('Rain rate', ''),
    ('Rain total', ''),
    ('Wind average speed', ''),
    ('Wind gust', ''),
    ('Chill', ''),
    ('Battery numeric', '%'),
    ('Rssi numeric', '')])


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the rfxtrx platform. """
    logger = logging.getLogger(__name__)

    devices = {}    # keep track of devices added to HA

    def sensor_update(event):
        """ Callback for sensor updates from the MySensors gateway. """
        if event.device.id_string in devices:
            devices[event.device.id_string].event = event
        else:
            logger.info("adding new devices: %s", event.device.type_string)
            new_device = RfxtrxSensor(event)
            devices[event.device.id_string] = new_device
            add_devices([new_device])
    try:
        import RFXtrx as rfxtrx
    except ImportError:
        logger.exception(
            "Failed to import rfxtrx")
        return False

    device = config.get("device", True)
    rfxtrx.Core(device, sensor_update)


class RfxtrxSensor(Entity):
    """ Represents a Vera Sensor. """

    def __init__(self, event):
        self.event = event

        self._unit_of_measurement = None
        self._data_type = None
        for data_type in DATA_TYPES:
            if data_type in self.event.values:
                self._unit_of_measurement = DATA_TYPES[data_type]
                self._data_type = data_type
                break

        id_string = int(event.device.id_string.replace(":", ""), 16)
        self._name = "{} {} ({})".format(self._data_type,
                                         self.event.device.type_string,
                                         id_string)

    def __str__(self):
        return self._name

    @property
    def state(self):
        if self._data_type:
            return self.event.values[self._data_type]
        return None

    @property
    def name(self):
        """ Get the mame of the sensor. """
        return self._name

    @property
    def state_attributes(self):
        return self.event.values

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
