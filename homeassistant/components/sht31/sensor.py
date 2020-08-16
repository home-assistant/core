"""Support for Sensirion SHT31 temperature and humidity sensor."""

from datetime import timedelta
import logging
import math

from Adafruit_SHT31 import SHT31
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.temperature import display_temp
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = "i2c_address"

DEFAULT_NAME = "SHT31"
DEFAULT_I2C_ADDRESS = 0x44

SENSOR_TEMPERATURE = "temperature"
SENSOR_HUMIDITY = "humidity"
SENSOR_TYPES = (SENSOR_TEMPERATURE, SENSOR_HUMIDITY)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.All(
            vol.Coerce(int), vol.Range(min=0x44, max=0x45)
        ),
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    i2c_address = config.get(CONF_I2C_ADDRESS)
    sensor = SHT31(address=i2c_address)

    try:
        if sensor.read_status() is None:
            raise ValueError("CRC error while reading SHT31 status")
    except (OSError, ValueError):
        _LOGGER.error("SHT31 sensor not detected at address %s", hex(i2c_address))
        return
    sensor_client = SHTClient(sensor)

    sensor_classes = {
        SENSOR_TEMPERATURE: SHTSensorTemperature,
        SENSOR_HUMIDITY: SHTSensorHumidity,
    }

    devs = []
    for sensor_type, sensor_class in sensor_classes.items():
        name = "{} {}".format(config.get(CONF_NAME), sensor_type.capitalize())
        devs.append(sensor_class(sensor_client, name))

    add_entities(devs)


class SHTClient:
    """Get the latest data from the SHT sensor."""

    def __init__(self, adafruit_sht):
        """Initialize the sensor."""
        self.adafruit_sht = adafruit_sht
        self.temperature = None
        self.humidity = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the SHT sensor."""
        temperature, humidity = self.adafruit_sht.read_temperature_humidity()
        if math.isnan(temperature) or math.isnan(humidity):
            _LOGGER.warning("Bad sample from sensor SHT31")
            return
        self.temperature = temperature
        self.humidity = humidity


class SHTSensor(Entity):
    """An abstract SHTSensor, can be either temperature or humidity."""

    def __init__(self, sensor, name):
        """Initialize the sensor."""
        self._sensor = sensor
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch temperature and humidity from the sensor."""
        self._sensor.update()


class SHTSensorTemperature(SHTSensor):
    """Representation of a temperature sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.hass.config.units.temperature_unit

    def update(self):
        """Fetch temperature from the sensor."""
        super().update()
        temp_celsius = self._sensor.temperature
        if temp_celsius is not None:
            self._state = display_temp(
                self.hass, temp_celsius, TEMP_CELSIUS, PRECISION_TENTHS
            )


class SHTSensorHumidity(SHTSensor):
    """Representation of a humidity sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UNIT_PERCENTAGE

    def update(self):
        """Fetch humidity from the sensor."""
        super().update()
        humidity = self._sensor.humidity
        if humidity is not None:
            self._state = round(humidity)
