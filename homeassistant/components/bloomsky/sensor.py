"""Support the sensor of a BloomSky weather station."""
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONF_MONITORED_CONDITIONS,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    PERCENTAGE,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

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
    "Pressure": PRESSURE_INHG,
    "Luminance": f"cd/{AREA_SQUARE_METERS}",
    "Voltage": ELECTRIC_POTENTIAL_MILLIVOLT,
}

# Metric units
SENSOR_UNITS_METRIC = {
    "Temperature": TEMP_CELSIUS,
    "Humidity": PERCENTAGE,
    "Pressure": PRESSURE_MBAR,
    "Luminance": f"cd/{AREA_SQUARE_METERS}",
    "Voltage": ELECTRIC_POTENTIAL_MILLIVOLT,
}

# Device class
SENSOR_DEVICE_CLASS = {
    "Temperature": DEVICE_CLASS_TEMPERATURE,
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


class BloomSkySensor(SensorEntity):
    """Representation of a single sensor in a BloomSky device."""

    def __init__(self, bs, device, sensor_name):
        """Initialize a BloomSky sensor."""
        self._bloomsky = bs
        self._device_id = device["DeviceID"]
        self._sensor_name = sensor_name
        self._attr_name = f"{device['DeviceName']} {sensor_name}"
        self._attr_unique_id = f"{self._device_id}-{sensor_name}"
        self._attr_native_unit_of_measurement = SENSOR_UNITS_IMPERIAL.get(
            sensor_name, None
        )
        if self._bloomsky.is_metric:
            self._attr_native_unit_of_measurement = SENSOR_UNITS_METRIC.get(
                sensor_name, None
            )

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SENSOR_DEVICE_CLASS.get(self._sensor_name)

    def update(self):
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()
        state = self._bloomsky.devices[self._device_id]["Data"][self._sensor_name]
        self._attr_native_value = (
            f"{state:.2f}" if self._sensor_name in FORMAT_NUMBERS else state
        )
