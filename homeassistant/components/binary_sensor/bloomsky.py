"""
Support the binary sensors of a BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.bloomsky/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.loader import get_component

DEPENDENCIES = ["bloomsky"]

# These are the available sensors mapped to binary_sensor class
SENSOR_TYPES = {
    "Rain": "moisture",
    "Night": None,
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the available BloomSky weather binary sensors."""
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


class BloomSkySensor(BinarySensorDevice):
    """Represent a single binary sensor in a BloomSky device."""

    def __init__(self, bs, device, sensor_name):
        """Initialize a BloomSky binary sensor."""
        self._bloomsky = bs
        self._device_id = device["DeviceID"]
        self._sensor_name = sensor_name
        self._name = "{} {}".format(device["DeviceName"], sensor_name)
        self._unique_id = "bloomsky_binary_sensor {}".format(self._name)
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
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return SENSOR_TYPES.get(self._sensor_name)

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return self._state

    def update(self):
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()

        self._state = \
            self._bloomsky.devices[self._device_id]["Data"][self._sensor_name]
