"""
Binary sensor support for the Skybell HD Doorbell.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.skybell/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.skybell import (
    DEFAULT_ENTITY_NAMESPACE, DOMAIN as SKYBELL_DOMAIN, SkybellDevice)

from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS)

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)

DEPENDENCIES = ['skybell']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

# Sensor types: Name, device_class, event
SENSOR_TYPES = {
    'button': ['Button', 'occupancy', 'device:sensor:button'],
    'motion': ['Motion', 'motion', 'device:sensor:motion'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the platform for a Skybell device."""
    skybell = hass.data.get(SKYBELL_DOMAIN)

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        for device in skybell.get_devices():
            sensors.append(SkybellBinarySensor(device, sensor_type))

    add_devices(sensors, True)
    return True


class SkybellBinarySensor(SkybellDevice, BinarySensorDevice):
    """A binary sensor implementation for Skybell devices."""

    def __init__(self, device, sensor_type):
        """Initialize a binary sensor for a Skybell device."""
        SkybellDevice.__init__(self, device)
        self._sensor_type = sensor_type
        self._name = "{0} {1}".format(self._device.name,
                                      SENSOR_TYPES.get(self._sensor_type)[0])
        self._device_class = SENSOR_TYPES.get(self._sensor_type)[1]
        self._event = None
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = super().device_state_attributes

        attrs['event_date'] = self._event['createdAt']

        return attrs

    def update(self):
        """Get the latest data and updates the state."""
        SkybellDevice.update(self)

        event = self._device.latest(SENSOR_TYPES.get(self._sensor_type)[2])

        if not self._event:
            self._event = event

        self._state = bool(event and event['id'] != self._event['id'])

        self._event = event
