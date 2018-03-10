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
    TEMP_FAHRENHEIT, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.util.temperature import celsius_to_fahrenheit

REQUIREMENTS = ['Adafruit-GPIO==1.0.3',
                'Adafruit-SHT31==1.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = 'i2c_address'

DEFAULT_NAME = 'SHT31'
DEFAULT_I2C_ADDRESS = '0x44'

SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'
SENSOR_TYPES = {
    SENSOR_TEMPERATURE: ['Temperature', lambda hass: hass.config.units.temperature_unit],
    SENSOR_HUMIDITY: ['Humidity', '%']
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

    i2c_address = int(config.get(CONF_I2C_ADDRESS), 16)
    sensor = SHT31(address=i2c_address)

    try:
        sensor.read_status()
    except OSError as err:
        raise HomeAssistantError("SHT31 sensor not detected at address %d (i2c_address: %s)" %
                                 (i2c_address, config.get(CONF_I2C_ADDRESS)))

    devs = []
    for sensor_type, props in SENSOR_TYPES.items():
        type_description, unit = props
        if callable(unit):
            unit = unit(hass)
        name = "{} {}".format(config.get(CONF_NAME), type_description)
        devs.append(SHTSensor(sensor, name, sensor_type, unit))

    add_devices(devs)


class SHTSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, sensor, name, sensor_type, unit):
        """Initialize the sensor."""
        self._sensor = sensor
        self._name = name
        self._type = sensor_type
        self._unit = unit
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
        return self._unit

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        if self._type == SENSOR_TEMPERATURE:
            temperature = self._sensor.read_temperature()
            if not math.isnan(temperature):
                self._state = round(temperature, 1)
                if self._unit == TEMP_FAHRENHEIT:
                    self._state = round(celsius_to_fahrenheit(temperature), 1)
            else:
                _LOGGER.warning("Bad sample from sensor %s", self.name)
        elif self._type == SENSOR_HUMIDITY:
            humidity = self._sensor.read_humidity()
            if not math.isnan(humidity):
                self._state = round(humidity)
            else:
                _LOGGER.warning("Bad sample from sensor %s", self.name)
