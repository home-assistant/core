"""
homeassistant.components.sensor.tellstick
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shows sensor values from tellstick sensors.

Possible config keys:

id of the sensor: Name the sensor with ID
135=Outside

only_named: Only show the named sensors
only_named=1

temperature_scale: The scale of the temperature value
temperature_scale=°C

datatype_mask: mask to determine which sensor values to show based on
https://tellcore-py.readthedocs.org
    /en/v1.0.4/constants.html#module-tellcore.constants

datatype_mask=1   # only show temperature
datatype_mask=12  # only show rain rate and rain total
datatype_mask=127 # show all sensor values
"""
import logging
from collections import namedtuple

import tellcore.telldus as telldus
import tellcore.constants as tellcore_constants

from homeassistant.const import TEMP_CELCIUS
from homeassistant.helpers.entity import Entity
import homeassistant.util as util

DatatypeDescription = namedtuple("DatatypeDescription", ['name', 'unit'])


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up Tellstick sensors. """
    sensor_value_descriptions = {
        tellcore_constants.TELLSTICK_TEMPERATURE:
        DatatypeDescription(
            'temperature', config.get('temperature_scale', TEMP_CELCIUS)),

        tellcore_constants.TELLSTICK_HUMIDITY:
        DatatypeDescription('humidity', '%'),

        tellcore_constants.TELLSTICK_RAINRATE:
        DatatypeDescription('rain rate', ''),

        tellcore_constants.TELLSTICK_RAINTOTAL:
        DatatypeDescription('rain total', ''),

        tellcore_constants.TELLSTICK_WINDDIRECTION:
        DatatypeDescription('wind direction', ''),

        tellcore_constants.TELLSTICK_WINDAVERAGE:
        DatatypeDescription('wind average', ''),

        tellcore_constants.TELLSTICK_WINDGUST:
        DatatypeDescription('wind gust', '')
    }

    try:
        core = telldus.TelldusCore()
    except OSError:
        logging.getLogger(__name__).exception(
            'Could not initialize Tellstick.')
        return

    sensors = []
    datatype_mask = util.convert(config.get('datatype_mask'), int, 127)

    for ts_sensor in core.sensors():
        try:
            sensor_name = config[ts_sensor.id]
        except KeyError:
            if 'only_named' in config:
                continue
            sensor_name = str(ts_sensor.id)

        for datatype in sensor_value_descriptions.keys():
            if datatype & datatype_mask and ts_sensor.has_value(datatype):

                sensor_info = sensor_value_descriptions[datatype]

                sensors.append(
                    TellstickSensor(
                        sensor_name, ts_sensor, datatype, sensor_info))

    add_devices(sensors)


class TellstickSensor(Entity):
    """ Represents a Tellstick sensor. """

    def __init__(self, name, sensor, datatype, sensor_info):
        self.datatype = datatype
        self.sensor = sensor
        self._unit_of_measurement = sensor_info.unit or None

        self._name = "{} {}".format(name, sensor_info.name)

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self.sensor.value(self.datatype).value

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement
