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

SENSOR_TYPES = {
    "light": ["light", " ", "mdi:weather-sunny", None],
    "light_red": ["light_red", " ", "mdi:invert-colors", None],
    "light_green": ["light_green", " ", "mdi:invert-colors", None],
    "light_blue": ["light_blue", " ", "mdi:invert-colors", None],
    "accelerometer_x": ["accelerometer_x", "G", "mdi:earth", None],
    "accelerometer_y": ["accelerometer_y", "G", "mdi:earth", None],
    "accelerometer_z": ["accelerometer_z", "G", "mdi:earth", None],
    "magnetometer_x": ["magnetometer_x", " ", "mdi:magnet", None],
    "magnetometer_y": ["magnetometer_y", " ", "mdi:magnet", None],
    "magnetometer_z": ["magnetometer_z", " ", "mdi:magnet", None],
    "temperature": ["temperature", TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    "pressure": ["pressure", PRESSURE_HPA, "mdi:gauge", None],
    "voltage_0": ["voltage_0", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "voltage_1": ["voltage_1", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "voltage_2": ["voltage_2", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
    "voltage_3": ["voltage_3", ELECTRIC_POTENTIAL_VOLT, "mdi:flash", None],
}

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
        self._name = SENSOR_TYPES[sensor_types][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_types][1]
        self.type = sensor_types
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SENSOR_TYPES[self.type][3]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

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
