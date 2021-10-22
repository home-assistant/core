"""Support for Enviro pHAT sensors."""
from __future__ import annotations

from datetime import timedelta
import importlib
import logging

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
    ELECTRIC_POTENTIAL_VOLT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "envirophat"
CONF_USE_LEDS = "use_leds"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="light",
        name="light",
        icon="mdi:weather-sunny",
    ),
    SensorEntityDescription(
        key="light_red",
        name="light_red",
        icon="mdi:invert-colors",
    ),
    SensorEntityDescription(
        key="light_green",
        name="light_green",
        icon="mdi:invert-colors",
    ),
    SensorEntityDescription(
        key="light_blue",
        name="light_blue",
        icon="mdi:invert-colors",
    ),
    SensorEntityDescription(
        key="accelerometer_x",
        name="accelerometer_x",
        native_unit_of_measurement="G",
        icon="mdi:earth",
    ),
    SensorEntityDescription(
        key="accelerometer_y",
        name="accelerometer_y",
        native_unit_of_measurement="G",
        icon="mdi:earth",
    ),
    SensorEntityDescription(
        key="accelerometer_z",
        name="accelerometer_z",
        native_unit_of_measurement="G",
        icon="mdi:earth",
    ),
    SensorEntityDescription(
        key="magnetometer_x",
        name="magnetometer_x",
        icon="mdi:magnet",
    ),
    SensorEntityDescription(
        key="magnetometer_y",
        name="magnetometer_y",
        icon="mdi:magnet",
    ),
    SensorEntityDescription(
        key="magnetometer_z",
        name="magnetometer_z",
        icon="mdi:magnet",
    ),
    SensorEntityDescription(
        key="temperature",
        name="temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    SensorEntityDescription(
        key="pressure",
        name="pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="voltage_0",
        name="voltage_0",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="voltage_1",
        name="voltage_1",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="voltage_2",
        name="voltage_2",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="voltage_3",
        name="voltage_3",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        icon="mdi:flash",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DISPLAY_OPTIONS, default=SENSOR_KEYS): [vol.In(SENSOR_KEYS)],
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_USE_LEDS, default=False): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Sense HAT sensor platform."""
    try:
        envirophat = importlib.import_module("envirophat")
    except OSError:
        _LOGGER.error("No Enviro pHAT was found")
        return False

    data = EnvirophatData(envirophat, config.get(CONF_USE_LEDS))

    display_options = config[CONF_DISPLAY_OPTIONS]
    entities = [
        EnvirophatSensor(data, description)
        for description in SENSOR_TYPES
        if description.key in display_options
    ]
    add_entities(entities, True)


class EnvirophatSensor(SensorEntity):
    """Representation of an Enviro pHAT sensor."""

    def __init__(self, data, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self.data = data

    def update(self):
        """Get the latest data and updates the states."""
        self.data.update()

        sensor_type = self.entity_description.key
        if sensor_type == "light":
            self._attr_native_value = self.data.light
        elif sensor_type == "light_red":
            self._attr_native_value = self.data.light_red
        elif sensor_type == "light_green":
            self._attr_native_value = self.data.light_green
        elif sensor_type == "light_blue":
            self._attr_native_value = self.data.light_blue
        elif sensor_type == "accelerometer_x":
            self._attr_native_value = self.data.accelerometer_x
        elif sensor_type == "accelerometer_y":
            self._attr_native_value = self.data.accelerometer_y
        elif sensor_type == "accelerometer_z":
            self._attr_native_value = self.data.accelerometer_z
        elif sensor_type == "magnetometer_x":
            self._attr_native_value = self.data.magnetometer_x
        elif sensor_type == "magnetometer_y":
            self._attr_native_value = self.data.magnetometer_y
        elif sensor_type == "magnetometer_z":
            self._attr_native_value = self.data.magnetometer_z
        elif sensor_type == "temperature":
            self._attr_native_value = self.data.temperature
        elif sensor_type == "pressure":
            self._attr_native_value = self.data.pressure
        elif sensor_type == "voltage_0":
            self._attr_native_value = self.data.voltage_0
        elif sensor_type == "voltage_1":
            self._attr_native_value = self.data.voltage_1
        elif sensor_type == "voltage_2":
            self._attr_native_value = self.data.voltage_2
        elif sensor_type == "voltage_3":
            self._attr_native_value = self.data.voltage_3


class EnvirophatData:
    """Get the latest data and update."""

    def __init__(self, envirophat, use_leds):
        """Initialize the data object."""
        self.envirophat = envirophat
        self.use_leds = use_leds
        # sensors readings
        self.light = None
        self.light_red = None
        self.light_green = None
        self.light_blue = None
        self.accelerometer_x = None
        self.accelerometer_y = None
        self.accelerometer_z = None
        self.magnetometer_x = None
        self.magnetometer_y = None
        self.magnetometer_z = None
        self.temperature = None
        self.pressure = None
        self.voltage_0 = None
        self.voltage_1 = None
        self.voltage_2 = None
        self.voltage_3 = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Enviro pHAT."""
        # Light sensor reading: 16-bit integer
        self.light = self.envirophat.light.light()
        if self.use_leds:
            self.envirophat.leds.on()
        # the three color values scaled against the overall light, 0-255
        self.light_red, self.light_green, self.light_blue = self.envirophat.light.rgb()
        if self.use_leds:
            self.envirophat.leds.off()

        # accelerometer readings in G
        (
            self.accelerometer_x,
            self.accelerometer_y,
            self.accelerometer_z,
        ) = self.envirophat.motion.accelerometer()

        # raw magnetometer reading
        (
            self.magnetometer_x,
            self.magnetometer_y,
            self.magnetometer_z,
        ) = self.envirophat.motion.magnetometer()

        # temperature resolution of BMP280 sensor: 0.01°C
        self.temperature = round(self.envirophat.weather.temperature(), 2)

        # pressure resolution of BMP280 sensor: 0.16 Pa, rounding to 0.1 Pa
        # with conversion to 100 Pa = 1 hPa
        self.pressure = round(self.envirophat.weather.pressure() / 100.0, 3)

        # Voltage sensor, reading between 0-3.3V
        (
            self.voltage_0,
            self.voltage_1,
            self.voltage_2,
            self.voltage_3,
        ) = self.envirophat.analog.read_all()
