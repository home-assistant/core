"""Support for Sense HAT sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
from pathlib import Path

from sense_hat import SenseHat
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_DISPLAY_OPTIONS,
    CONF_NAME,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "sensehat"
CONF_IS_HAT_ATTACHED = "is_hat_attached"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        name="temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        name="humidity",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="pressure",
        name="pressure",
        native_unit_of_measurement="mb",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DISPLAY_OPTIONS, default=SENSOR_KEYS): [vol.In(SENSOR_KEYS)],
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_IS_HAT_ATTACHED, default=True): cv.boolean,
    }
)


def get_cpu_temp():
    """Get CPU temperature."""
    t_cpu = (
        Path("/sys/class/thermal/thermal_zone0/temp")
        .read_text(encoding="utf-8")
        .strip()
    )
    return float(t_cpu) * 0.001


def get_average(temp_base):
    """Use moving average to get better readings."""
    if not hasattr(get_average, "temp"):
        get_average.temp = [temp_base, temp_base, temp_base]
    get_average.temp[2] = get_average.temp[1]
    get_average.temp[1] = get_average.temp[0]
    get_average.temp[0] = temp_base
    temp_avg = (get_average.temp[0] + get_average.temp[1] + get_average.temp[2]) / 3
    return temp_avg


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sense HAT sensor platform."""
    data = SenseHatData(config.get(CONF_IS_HAT_ATTACHED))
    display_options = config[CONF_DISPLAY_OPTIONS]
    entities = [
        SenseHatSensor(data, description)
        for description in SENSOR_TYPES
        if description.key in display_options
    ]

    add_entities(entities, True)


class SenseHatSensor(SensorEntity):
    """Representation of a Sense HAT sensor."""

    def __init__(self, data, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.data = data

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()
        if not self.data.humidity:
            _LOGGER.error("Don't receive data")
            return

        sensor_type = self.entity_description.key
        if sensor_type == "temperature":
            self._attr_native_value = self.data.temperature
        elif sensor_type == "humidity":
            self._attr_native_value = self.data.humidity
        elif sensor_type == "pressure":
            self._attr_native_value = self.data.pressure


class SenseHatData:
    """Get the latest data and update."""

    def __init__(self, is_hat_attached):
        """Initialize the data object."""
        self.temperature = None
        self.humidity = None
        self.pressure = None
        self.is_hat_attached = is_hat_attached

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Sense HAT."""

        sense = SenseHat()
        temp_from_h = sense.get_temperature_from_humidity()
        temp_from_p = sense.get_temperature_from_pressure()
        t_total = (temp_from_h + temp_from_p) / 2

        if self.is_hat_attached:
            t_cpu = get_cpu_temp()
            t_correct = t_total - ((t_cpu - t_total) / 1.5)
            t_correct = get_average(t_correct)
        else:
            t_correct = get_average(t_total)

        self.temperature = t_correct
        self.humidity = sense.get_humidity()
        self.pressure = sense.get_pressure()
