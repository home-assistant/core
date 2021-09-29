"""Support for Sensirion SHT31 temperature and humidity sensor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
import math

from Adafruit_SHT31 import SHT31
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = "i2c_address"

DEFAULT_NAME = "SHT31"
DEFAULT_I2C_ADDRESS = 0x44


@dataclass
class SHT31RequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[SHTClient], float | None]


@dataclass
class SHT31SensorEntityDescription(SensorEntityDescription, SHT31RequiredKeysMixin):
    """Describes SHT31 sensor entity."""


SENSOR_TYPES = (
    SHT31SensorEntityDescription(
        key="temperature",
        name="Temperature",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        value_fn=lambda sensor: sensor.temperature,
    ),
    SHT31SensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda sensor: (
            round(val)  # pylint: disable=undefined-variable
            if (val := sensor.humidity)
            else None
        ),
    ),
)
SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.All(
            vol.Coerce(int), vol.Range(min=0x44, max=0x45)
        ),
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    name = config[CONF_NAME]
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    i2c_address = config[CONF_I2C_ADDRESS]
    sensor = SHT31(address=i2c_address)

    try:
        if sensor.read_status() is None:
            raise ValueError("CRC error while reading SHT31 status")
    except (OSError, ValueError):
        _LOGGER.error("SHT31 sensor not detected at address %s", hex(i2c_address))
        return
    sensor_client = SHTClient(sensor)

    entities = [
        SHTSensor(sensor_client, name, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
    ]

    add_entities(entities)


class SHTClient:
    """Get the latest data from the SHT sensor."""

    def __init__(self, adafruit_sht):
        """Initialize the sensor."""
        self.adafruit_sht = adafruit_sht
        self.temperature: float | None = None
        self.humidity: float | None = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the SHT sensor."""
        temperature, humidity = self.adafruit_sht.read_temperature_humidity()
        if math.isnan(temperature) or math.isnan(humidity):
            _LOGGER.warning("Bad sample from sensor SHT31")
            return
        self.temperature = temperature
        self.humidity = humidity


class SHTSensor(SensorEntity):
    """An abstract SHTSensor, can be either temperature or humidity."""

    entity_description: SHT31SensorEntityDescription

    def __init__(self, sensor, name, description: SHT31SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._sensor = sensor

        self._attr_name = f"{name} {description.name}"

    def update(self):
        """Fetch temperature and humidity from the sensor."""
        self._sensor.update()
        self._attr_native_value = self.entity_description.value_fn(self._sensor)
