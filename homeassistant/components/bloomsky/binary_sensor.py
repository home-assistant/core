"""Support the binary sensors of a BloomSky weather station."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOISTURE,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {"Rain": DEVICE_CLASS_MOISTURE, "Night": None}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        )
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the available BloomSky weather binary sensors."""
    # Default needed in case of discovery
    if discovery_info is not None:
        return

    sensors = config[CONF_MONITORED_CONDITIONS]
    bloomsky = hass.data[DOMAIN]

    for device in bloomsky.devices.values():
        for variable in sensors:
            add_entities([BloomSkySensor(bloomsky, device, variable)], True)


class BloomSkySensor(BinarySensorEntity):
    """Representation of a single binary sensor in a BloomSky device."""

    def __init__(self, bs, device, sensor_name):
        """Initialize a BloomSky binary sensor."""
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
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return SENSOR_TYPES.get(self._sensor_name)

    @property
    def is_on(self):
        """Return true if binary sensor is on."""
        return self._state

    def update(self):
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()

        self._state = self._bloomsky.devices[self._device_id]["Data"][self._sensor_name]
