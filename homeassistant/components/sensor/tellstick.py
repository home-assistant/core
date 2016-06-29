"""
Support for Tellstick sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tellstick/
"""
import logging
from collections import namedtuple

import homeassistant.util as util
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

DatatypeDescription = namedtuple("DatatypeDescription", ['name', 'unit'])

REQUIREMENTS = ['tellcore-py==1.1.2']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Tellstick sensors."""
    import tellcore.telldus as telldus
    import tellcore.constants as tellcore_constants

    sensor_value_descriptions = {
        tellcore_constants.TELLSTICK_TEMPERATURE:
        DatatypeDescription(
            'temperature', config.get('temperature_scale', TEMP_CELSIUS)),

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
            if util.convert(config.get('only_named'), bool, False):
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
    """Representation of a Tellstick sensor."""

    def __init__(self, name, sensor, datatype, sensor_info):
        """Initialize the sensor."""
        self.datatype = datatype
        self.sensor = sensor
        self._unit_of_measurement = sensor_info.unit or None

        self._name = "{} {}".format(name, sensor_info.name)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.sensor.value(self.datatype).value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
