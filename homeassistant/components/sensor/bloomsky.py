"""
Support the sensor of a BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.bloomsky/
"""
import logging

from homeassistant.const import TEMP_FAHRENHEIT
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

DEPENDENCIES = ["bloomsky"]

# These are the available sensors
SENSOR_TYPES = ["Temperature",
                "Humidity",
                "Pressure",
                "Luminance",
                "UVIndex"]

# Sensor units - these do not currently align with the API documentation
SENSOR_UNITS = {"Temperature": TEMP_FAHRENHEIT,
                "Humidity": "%",
                "Pressure": "inHg",
                "Luminance": "cd/m²"}

# Which sensors to format numerically
FORMAT_NUMBERS = ["Temperature", "Pressure"]


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available BloomSky weather sensors."""
    logger = logging.getLogger(__name__)
    bloomsky = get_component('bloomsky')
    sensors = config.get('monitored_conditions', SENSOR_TYPES)

    for device in bloomsky.BLOOMSKY.devices.values():
        for variable in sensors:
            if variable in SENSOR_TYPES:
                add_devices([BloomSkySensor(bloomsky.BLOOMSKY,
                                            device,
                                            variable)])
            else:
                logger.error("Cannot find definition for device: %s", variable)


class BloomSkySensor(Entity):
    """Representation of a single sensor in a BloomSky device."""

    def __init__(self, bs, device, sensor_name):
        """Initialize a bloomsky sensor."""
        self._bloomsky = bs
        self._device_id = device["DeviceID"]
        self._sensor_name = sensor_name
        self._name = "{} {}".format(device["DeviceName"], sensor_name)
        self._unique_id = "bloomsky_sensor {}".format(self._name)
        self.update()

    @property
    def name(self):
        """The name of the BloomSky device and this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

    @property
    def state(self):
        """The current state, eg. value, of this sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the sensor units."""
        return SENSOR_UNITS.get(self._sensor_name, None)

    def update(self):
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()

        state = \
            self._bloomsky.devices[self._device_id]["Data"][self._sensor_name]

        if self._sensor_name in FORMAT_NUMBERS:
            self._state = "{0:.2f}".format(state)
        else:
            self._state = state
