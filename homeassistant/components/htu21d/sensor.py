"""Support for HTU21D temperature and humidity sensor."""
from datetime import timedelta
from functools import partial
import logging

from i2csense.htu21d import HTU21D  # pylint: disable=import-error
import smbus
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.temperature import celsius_to_fahrenheit

_LOGGER = logging.getLogger(__name__)

CONF_I2C_BUS = "i2c_bus"
DEFAULT_I2C_BUS = 1

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

DEFAULT_NAME = "HTU21D Sensor"

SENSOR_TEMPERATURE = "temperature"
SENSOR_HUMIDITY = "humidity"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
    }
)

DEVICE_CLASS_MAP = {
    SENSOR_TEMPERATURE: DEVICE_CLASS_TEMPERATURE,
    SENSOR_HUMIDITY: DEVICE_CLASS_HUMIDITY,
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HTU21D sensor."""
    name = config.get(CONF_NAME)
    bus_number = config.get(CONF_I2C_BUS)
    temp_unit = hass.config.units.temperature_unit

    bus = smbus.SMBus(config.get(CONF_I2C_BUS))
    sensor = await hass.async_add_executor_job(partial(HTU21D, bus, logger=_LOGGER))
    if not sensor.sample_ok:
        _LOGGER.error("HTU21D sensor not detected in bus %s", bus_number)
        return False

    sensor_handler = await hass.async_add_executor_job(HTU21DHandler, sensor)

    dev = [
        HTU21DSensor(sensor_handler, name, SENSOR_TEMPERATURE, temp_unit),
        HTU21DSensor(sensor_handler, name, SENSOR_HUMIDITY, PERCENTAGE),
    ]

    async_add_entities(dev)


class HTU21DHandler:
    """Implement HTU21D communication."""

    def __init__(self, sensor):
        """Initialize the sensor handler."""
        self.sensor = sensor
        self.sensor.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Read raw data and calculate temperature and humidity."""
        self.sensor.update()


class HTU21DSensor(SensorEntity):
    """Implementation of the HTU21D sensor."""

    def __init__(self, htu21d_client, name, variable, unit):
        """Initialize the sensor."""
        self._name = f"{name}_{variable}"
        self._variable = variable
        self._unit_of_measurement = unit
        self._client = htu21d_client
        self._state = None
        self._attr_device_class = DEVICE_CLASS_MAP[variable]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data from the HTU21D sensor and update the state."""
        await self.hass.async_add_executor_job(self._client.update)
        if self._client.sensor.sample_ok:
            if self._variable == SENSOR_TEMPERATURE:
                value = round(self._client.sensor.temperature, 1)
                if self.unit_of_measurement == TEMP_FAHRENHEIT:
                    value = celsius_to_fahrenheit(value)
            else:
                value = round(self._client.sensor.humidity, 1)
            self._state = value
        else:
            _LOGGER.warning("Bad sample")
