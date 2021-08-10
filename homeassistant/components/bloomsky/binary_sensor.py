"""Support the binary sensors of a BloomSky weather station."""
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOISTURE,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv

from . import DOMAIN

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
        self._attr_name = f"{device['DeviceName']} {sensor_name}"
        self._attr_unique_id = f"{self._device_id}-{sensor_name}"
        self._attr_device_class = SENSOR_TYPES.get(sensor_name)

    def update(self):
        """Request an update from the BloomSky API."""
        self._bloomsky.refresh_devices()

        self._attr_is_on = self._bloomsky.devices[self._device_id]["Data"][
            self._sensor_name
        ]
