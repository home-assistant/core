"""Support the sensor of a BloomSky weather station."""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    PERCENTAGE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from . import DOMAIN

LOGGER = logging.getLogger(__name__)

# These are the available sensors
SENSOR_TYPES = [
    "Temperature",
    "Humidity",
    "Pressure",
    "Luminance",
    "UVIndex",
    "Voltage",
]

# Sensor units - these do not currently align with the API documentation
SENSOR_UNITS_IMPERIAL = {
    "Temperature": TEMP_FAHRENHEIT,
    "Humidity": PERCENTAGE,
    "Pressure": "inHg",
    "Luminance": "cd/m²",
    "Voltage": "mV",
}

# Metric units
SENSOR_UNITS_METRIC = {
    "Temperature": TEMP_CELSIUS,
    "Humidity": PERCENTAGE,
    "Pressure": "mbar",
    "Luminance": "cd/m²",
    "Voltage": "mV",
}

# Which sensors to format numerically
FORMAT_NUMBERS = ["Temperature", "Pressure", "Voltage"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_TYPES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available BloomSky weather sensors."""
    # Default needed in case of discovery
    if discovery_info is not None:
        return

    sensors = config[CONF_MONITORED_CONDITIONS]
    bloomsky = hass.data[DOMAIN]

    for device in bloomsky.devices.values():
        for variable in sensors:
            add_entities([BloomSkySensor(bloomsky, device, variable)], True)


class BloomSkySensor(Entity):
    """Representation of a single sensor in a BloomSky device."""

    def __init__(self, bs, device, sensor_name):
        """Initialize a BloomSky sensor."""
        self._bloomsky = bs
        self._device_id = device["DeviceID"]
        self._sensor_name = sensor_name
        self._name = f"{device['DeviceName']} {sensor_name}"
        self._state = None
        self._unique_id = f"{self._device_id}-{self._sensor_name}"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the BloomSky device and this sensor."""
        return self._name

    @property
    def state(self):
        """Return the current state, eg. value, of this sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the sensor units."""
        if self._bloomsky.is_metric:
            return SENSOR_UNITS_METRIC.get(self._sensor_name, None)
        return SENSOR_UNITS_IMPERIAL.get(self._sensor_name, None)

    def update(self):
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()

        state = self._bloomsky.devices[self._device_id]["Data"][self._sensor_name]

        if self._sensor_name in FORMAT_NUMBERS:
            self._state = f"{state:.2f}"
        else:
            self._state = state
