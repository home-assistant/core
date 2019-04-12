"""Support for BME280 temperature, humidity and pressure sensor."""
from datetime import timedelta
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    TEMP_FAHRENHEIT, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.temperature import celsius_to_fahrenheit

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_OVERSAMPLING_TEMP = 'oversampling_temperature'
CONF_OVERSAMPLING_PRES = 'oversampling_pressure'
CONF_OVERSAMPLING_HUM = 'oversampling_humidity'
CONF_OPERATION_MODE = 'operation_mode'
CONF_T_STANDBY = 'time_standby'
CONF_FILTER_MODE = 'filter_mode'
CONF_DELTA_TEMP = 'delta_temperature'

DEFAULT_NAME = 'BME280 Sensor'
DEFAULT_I2C_ADDRESS = '0x76'
DEFAULT_I2C_BUS = 1
DEFAULT_OVERSAMPLING_TEMP = 1  # Temperature oversampling x 1
DEFAULT_OVERSAMPLING_PRES = 1  # Pressure oversampling x 1
DEFAULT_OVERSAMPLING_HUM = 1  # Humidity oversampling x 1
DEFAULT_OPERATION_MODE = 3  # Normal mode (forced mode: 2)
DEFAULT_T_STANDBY = 5  # Tstandby 5ms
DEFAULT_FILTER_MODE = 0  # Filter off
DEFAULT_DELTA_TEMP = 0.

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)

SENSOR_TEMP = 'temperature'
SENSOR_HUMID = 'humidity'
SENSOR_PRESS = 'pressure'
SENSOR_TYPES = {
    SENSOR_TEMP: ['Temperature', None],
    SENSOR_HUMID: ['Humidity', '%'],
    SENSOR_PRESS: ['Pressure', 'mb']
}
DEFAULT_MONITORED = [SENSOR_TEMP, SENSOR_HUMID, SENSOR_PRESS]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_TEMP,
                 default=DEFAULT_OVERSAMPLING_TEMP): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_PRES,
                 default=DEFAULT_OVERSAMPLING_PRES): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_HUM,
                 default=DEFAULT_OVERSAMPLING_HUM): vol.Coerce(int),
    vol.Optional(CONF_OPERATION_MODE,
                 default=DEFAULT_OPERATION_MODE): vol.Coerce(int),
    vol.Optional(CONF_T_STANDBY,
                 default=DEFAULT_T_STANDBY): vol.Coerce(int),
    vol.Optional(CONF_FILTER_MODE,
                 default=DEFAULT_FILTER_MODE): vol.Coerce(int),
    vol.Optional(CONF_DELTA_TEMP,
                 default=DEFAULT_DELTA_TEMP): vol.Coerce(float),
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the BME280 sensor."""
    import smbus  # pylint: disable=import-error
    from i2csense.bme280 import BME280  # pylint: disable=import-error

    SENSOR_TYPES[SENSOR_TEMP][1] = hass.config.units.temperature_unit
    name = config.get(CONF_NAME)
    i2c_address = config.get(CONF_I2C_ADDRESS)

    bus = smbus.SMBus(config.get(CONF_I2C_BUS))
    sensor = await hass.async_add_job(
        partial(BME280, bus, i2c_address,
                osrs_t=config.get(CONF_OVERSAMPLING_TEMP),
                osrs_p=config.get(CONF_OVERSAMPLING_PRES),
                osrs_h=config.get(CONF_OVERSAMPLING_HUM),
                mode=config.get(CONF_OPERATION_MODE),
                t_sb=config.get(CONF_T_STANDBY),
                filter_mode=config.get(CONF_FILTER_MODE),
                delta_temp=config.get(CONF_DELTA_TEMP),
                logger=_LOGGER)
    )
    if not sensor.sample_ok:
        _LOGGER.error("BME280 sensor not detected at %s", i2c_address)
        return False

    sensor_handler = await hass.async_add_job(BME280Handler, sensor)

    dev = []
    try:
        for variable in config[CONF_MONITORED_CONDITIONS]:
            dev.append(BME280Sensor(
                sensor_handler, variable, SENSOR_TYPES[variable][1], name))
    except KeyError:
        pass

    async_add_entities(dev, True)


class BME280Handler:
    """BME280 sensor working in i2C bus."""

    def __init__(self, sensor):
        """Initialize the sensor handler."""
        self.sensor = sensor
        self.update(True)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, first_reading=False):
        """Read sensor data."""
        self.sensor.update(first_reading)


class BME280Sensor(Entity):
    """Implementation of the BME280 sensor."""

    def __init__(self, bme280_client, sensor_type, temp_unit, name):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.bme280_client = bme280_client
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data from the BME280 and update the states."""
        await self.hass.async_add_job(self.bme280_client.update)
        if self.bme280_client.sensor.sample_ok:
            if self.type == SENSOR_TEMP:
                temperature = round(self.bme280_client.sensor.temperature, 1)
                if self.temp_unit == TEMP_FAHRENHEIT:
                    temperature = round(celsius_to_fahrenheit(temperature), 1)
                self._state = temperature
            elif self.type == SENSOR_HUMID:
                self._state = round(self.bme280_client.sensor.humidity, 1)
            elif self.type == SENSOR_PRESS:
                self._state = round(self.bme280_client.sensor.pressure, 1)
        else:
            _LOGGER.warning("Bad update of sensor.%s", self.name)
