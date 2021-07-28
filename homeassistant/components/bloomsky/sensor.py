"""Support the sensor of a BloomSky weather station."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    AREA_SQUARE_METERS,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    LENGTH_INCHES,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRECIPITATION_INCHES_PER_HOUR,
    PRECIPITATION_MILLIMETERS_PER_HOUR,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    UV_INDEX,
)

from . import DOMAIN

# See http://weatherlution.com/bloomsky-api/
# http://weatherlution.com/wp-content/uploads/2016/01/v1.6BloomskyDeviceOwnerAPIDocumentationforBusinessOwners.pdf

# These are the available sensors
SKY_SENSORS = [
    "Humidity",
    "Luminance",
    "Pressure",
    "Temperature",
    "UVIndex",  # Also on storm
    "Voltage",
]

STORM_SENSORS = [
    "24hRain",  # last 24hs
    "RainDaily",  # 12a-1159p
    "RainRate",  # last 10m
    "SustainedWindSpeed",
    "WindDirection",  # NW, etc
    "WindGust",
]

# Sensor units - these do not currently align with the API documentation
SENSOR_UNITS_IMPERIAL = {
    "24hRain": LENGTH_INCHES,
    "Humidity": PERCENTAGE,
    "Luminance": f"cd/{AREA_SQUARE_METERS}",
    "Pressure": PRESSURE_INHG,
    "RainDaily": LENGTH_INCHES,
    "RainRate": PRECIPITATION_INCHES_PER_HOUR,
    "SustainedWindSpeed": SPEED_MILES_PER_HOUR,
    "Temperature": TEMP_FAHRENHEIT,
    "UVIndex": UV_INDEX,
    "Voltage": ELECTRIC_POTENTIAL_MILLIVOLT,
    "WindGust": SPEED_MILES_PER_HOUR,
}

# Metric units
SENSOR_UNITS_METRIC = {
    "24hRain": LENGTH_MILLIMETERS,
    "Humidity": PERCENTAGE,
    "Luminance": f"cd/{AREA_SQUARE_METERS}",
    "Pressure": PRESSURE_MBAR,
    "RainDaily": LENGTH_MILLIMETERS,
    "RainRate": PRECIPITATION_MILLIMETERS_PER_HOUR,
    "SustainedWindSpeed": SPEED_METERS_PER_SECOND,
    "Temperature": TEMP_CELSIUS,
    "UVIndex": UV_INDEX,
    "Voltage": ELECTRIC_POTENTIAL_MILLIVOLT,
    "WindGust": SPEED_METERS_PER_SECOND,
}

# Device class
SENSOR_DEVICE_CLASS = {
    "Humidity": DEVICE_CLASS_HUMIDITY,
    "Luminance": DEVICE_CLASS_ILLUMINANCE,
    "Pressure": DEVICE_CLASS_PRESSURE,
    "Temperature": DEVICE_CLASS_TEMPERATURE,
    "Voltage": DEVICE_CLASS_BATTERY,
}

# Which sensors to format numerically
FORMAT_NUMBERS = [
    "24hRain",
    "Pressure",
    "RainDaily",
    "RainRate",
    "SustainedWindSpeed",
    "Temperature",
    "Voltage",
    "WindGust",
]


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available BloomSky weather sensors."""
    # Default needed in case of discovery
    if discovery_info is not None:
        return

    bloomsky = hass.data[DOMAIN]
    bloomsky.refresh_devices()

    for device in bloomsky.devices.values():
        add_entities(
            (BloomSkySensor(bloomsky, device, what) for what in SKY_SENSORS), True
        )
        if "Storm" in device:
            add_entities(
                (BloomSkySensor(bloomsky, device, what) for what in STORM_SENSORS), True
            )


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
        device = self._bloomsky.devices[self._device_id]
        data = {}
        data.update(device["Data"])
        # Storm supersedes sky data.
        data.update(device.get("Storm", {}))
        state = data[self._sensor_name]
        self._attr_native_value = (
            f"{state:.2f}" if self._sensor_name in FORMAT_NUMBERS else state
        )
