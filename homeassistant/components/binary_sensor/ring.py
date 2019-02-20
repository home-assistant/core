"""
This component provides HA sensor support for Ring Door Bell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ring/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.ring import (
    CONF_ATTRIBUTION, DEFAULT_ENTITY_NAMESPACE, DATA_RING)

from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS)

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)

DEPENDENCIES = ['ring']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

# Sensor types: Name, category, device_class
SENSOR_TYPES = {
    'ding': ['Ding', ['doorbell'], 'occupancy'],
    'motion': ['Motion', ['doorbell', 'stickup_cams'], 'motion'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a sensor for a Ring device."""
    ring = hass.data[DATA_RING]

    sensors = []
    for device in ring.doorbells:  # ring.doorbells is doing I/O
        for sensor_type in config[CONF_MONITORED_CONDITIONS]:
            if 'doorbell' in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingBinarySensor(hass,
                                                device,
                                                sensor_type))

    for device in ring.stickup_cams:  # ring.stickup_cams is doing I/O
        for sensor_type in config[CONF_MONITORED_CONDITIONS]:
            if 'stickup_cams' in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingBinarySensor(hass,
                                                device,
                                                sensor_type))
    add_entities(sensors, True)
    return True


class RingBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Ring device."""

    def __init__(self, hass, data, sensor_type):
        """Initialize a sensor for Ring device."""
        super(RingBinarySensor, self).__init__()
        self._sensor_type = sensor_type
        self._data = data
        self._name = "{0} {1}".format(self._data.name,
                                      SENSOR_TYPES.get(self._sensor_type)[0])
        self._device_class = SENSOR_TYPES.get(self._sensor_type)[2]
        self._state = None
        self._unique_id = '{}-{}'.format(self._data.id, self._sensor_type)

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
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

        attrs['device_id'] = self._data.id
        attrs['firmware'] = self._data.firmware
        attrs['timezone'] = self._data.timezone

        if self._data.alert and self._data.alert_expires_at:
            attrs['expires_at'] = self._data.alert_expires_at
            attrs['state'] = self._data.alert.get('state')

        return attrs

    def update(self):
        """Get the latest data and updates the state."""
        self._data.check_alerts()

        if self._data.alert:
            if self._sensor_type == self._data.alert.get('kind') and \
               self._data.account_id == self._data.alert.get('doorbot_id'):
                self._state = True
        else:
            self._state = False
