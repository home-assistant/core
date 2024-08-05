"""Support the sensor of a BloomSky weather station."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import (
    AREA_SQUARE_METERS,
    CONF_MONITORED_CONDITIONS,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
    "Temperature": UnitOfTemperature.FAHRENHEIT,
    "Humidity": PERCENTAGE,
    "Pressure": UnitOfPressure.INHG,
    "Luminance": f"cd/{AREA_SQUARE_METERS}",
    "Voltage": UnitOfElectricPotential.MILLIVOLT,
}

# Metric units
SENSOR_UNITS_METRIC = {
    "Temperature": UnitOfTemperature.CELSIUS,
    "Humidity": PERCENTAGE,
    "Pressure": UnitOfPressure.MBAR,
    "Luminance": f"cd/{AREA_SQUARE_METERS}",
    "Voltage": UnitOfElectricPotential.MILLIVOLT,
}

# Device class
SENSOR_DEVICE_CLASS = {
    "Temperature": SensorDeviceClass.TEMPERATURE,
    "Humidity": SensorDeviceClass.HUMIDITY,
    "Pressure": SensorDeviceClass.PRESSURE,
    "Voltage": SensorDeviceClass.VOLTAGE,
}

# Which sensors to format numerically
FORMAT_NUMBERS = ["Temperature", "Pressure", "Voltage"]

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_TYPES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
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
        self._attr_device_class = SENSOR_DEVICE_CLASS.get(sensor_name)
        self._attr_native_unit_of_measurement = SENSOR_UNITS_IMPERIAL.get(sensor_name)
        if self._bloomsky.is_metric:
            self._attr_native_unit_of_measurement = SENSOR_UNITS_METRIC.get(sensor_name)

    def update(self) -> None:
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()
        state = self._bloomsky.devices[self._device_id]["Data"][self._sensor_name]
        self._attr_native_value = (
            f"{state:.2f}" if self._sensor_name in FORMAT_NUMBERS else state
        )
