"""
Support the binary sensors of a BloomSky weather station.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.bloomsky/
"""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.loader import get_component
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['bloomsky']

SENSOR_TYPES = {
    'Rain': 'moisture',
    'Night': None,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITIONS, default=SENSOR_TYPES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the available BloomSky weather binary sensors."""
    bloomsky = get_component('bloomsky')
    # Default needed in case of discovery
    sensors = config.get(CONF_MONITORED_CONDITIONS, SENSOR_TYPES)

    for device in bloomsky.BLOOMSKY.devices.values():
        for variable in sensors:
            add_devices([BloomSkySensor(bloomsky.BLOOMSKY, device, variable)])


class BloomSkySensor(BinarySensorDevice):
    """Representation of a single binary sensor in a BloomSky device."""

    def __init__(self, bs, device, sensor_name):
        """Initialize a BloomSky binary sensor."""
        self._bloomsky = bs
        self._device_id = device['DeviceID']
        self._sensor_name = sensor_name
        self._name = '{} {}'.format(device['DeviceName'], sensor_name)
        self._unique_id = 'bloomsky_binary_sensor {}'.format(self._name)
        self.update()

    @property
    def name(self):
        """Return the name of the BloomSky device and this sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique ID for this sensor."""
        return self._unique_id

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

        self._state = \
            self._bloomsky.devices[self._device_id]['Data'][self._sensor_name]
