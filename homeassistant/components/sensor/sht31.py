"""
Support for Sensirion SHT31 temperature and humidity sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sht31/
"""

import logging
import math
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    TEMP_CELSIUS, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.temperature import display_temp
from homeassistant.const import PRECISION_TENTHS

REQUIREMENTS = ['Adafruit-GPIO==1.0.3',
                'Adafruit-SHT31==1.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = 'i2c_address'

DEFAULT_NAME = 'SHT31'
DEFAULT_I2C_ADDRESS = 0x44

SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'
SENSOR_TYPES = {
    SENSOR_TEMPERATURE: 'Temperature',
    SENSOR_HUMIDITY: 'Humidity'
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES.keys())):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    from Adafruit_SHT31 import SHT31

    i2c_address = int(config.get(CONF_I2C_ADDRESS))
    sensor = SHT31(address=i2c_address)

    try:
        sensor.read_status()
    except OSError as err:
        raise HomeAssistantError("SHT31 sensor not detected at address %s " %
                                 hex(i2c_address))

    devs = []
    for sensor_type, type_description in SENSOR_TYPES.items():
        name = "{} {}".format(config.get(CONF_NAME), type_description)
        devs.append(SHTSensor(sensor, name, sensor_type))

    add_devices(devs)


class SHTSensor(Entity):
    """Representation of a SHTSensor, can be either temperature or humidity"""

    def __init__(self, sensor, name, sensor_type):
        """Initialize the sensor."""
        self._sensor = sensor
        self._name = name
        self._type = sensor_type
        self._state = None

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
        """Return the unit of measurement."""
        if self._type == SENSOR_TEMPERATURE:
            return self.hass.config.units.temperature_unit
        elif self._type == SENSOR_HUMIDITY:
            return '%'

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        if self._type == SENSOR_TEMPERATURE:
            temp_celsius = self._sensor.read_temperature()
            if not math.isnan(temp_celsius):
                self._state = display_temp(self.hass, temp_celsius,
                                           TEMP_CELSIUS, PRECISION_TENTHS)
            else:
                _LOGGER.warning("Bad sample from sensor %s", self.name)
        elif self._type == SENSOR_HUMIDITY:
            humidity = self._sensor.read_humidity()
            if not math.isnan(humidity):
                self._state = round(humidity)
            else:
                _LOGGER.warning("Bad sample from sensor %s", self.name)
