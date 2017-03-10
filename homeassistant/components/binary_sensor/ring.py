"""
This component provides HA sensor support for Ring Door Bell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.ring/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import homeassistant.loader as loader

from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS,
    CONF_USERNAME, CONF_PASSWORD, ATTR_ATTRIBUTION)

from requests.exceptions import HTTPError, ConnectTimeout

REQUIREMENTS = ['ring_doorbell==0.1.1']

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = 'ring_notification'
NOTIFICATION_TITLE = 'Ring Binary Sensor Setup'

DEFAULT_CACHEDB = 'ring_cache.pickle'
DEFAULT_ENTITY_NAMESPACE = 'ring'
SCAN_INTERVAL = timedelta(seconds=5)

CONF_ATTRIBUTION = "Data provided by Ring.com"

# Sensor types: Name, category, device_class
SENSOR_TYPES = {
    'ding': ['Ding', ['doorbell'], 'occupancy'],
    'motion': ['Motion', ['doorbell'], 'motion'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a Ring device."""
    from ring_doorbell import Ring
    ring = Ring(username=config.get(CONF_USERNAME),
                password=config.get(CONF_PASSWORD),
                persist_token=True)

    persistent_notification = loader.get_component('persistent_notification')
    try:
        ring.is_connected
    except (ConnectTimeout, HTTPError) as ex:
        _LOGGER.error("Unable to connect to Ring service: %s", str(ex))
        persistent_notification.create(
            hass, 'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        for device in ring.doorbells:
            if 'doorbell' in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingBinarySensor(hass,
                                                device,
                                                sensor_type))
    add_devices(sensors, True)
    return True


class RingBinarySensor(BinarySensorDevice):
    """A binary sensor implementation for Ring device."""

    def __init__(self, hass, data, sensor_type):
        """Initialize a sensor for Ring device."""
        super(RingBinarySensor, self).__init__()
        self._cache = hass.config.path(DEFAULT_CACHEDB)
        self._sensor_type = sensor_type
        self._data = data
        self._name = "{0} {1}".format(self._data.name,
                                      SENSOR_TYPES.get(self._sensor_type)[0])
        self._device_class = SENSOR_TYPES.get(self._sensor_type)[2]
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
        self._data.check_alerts(cache=self._cache)

        if self._data.alert:
            self._state = bool(self._sensor_type ==
                               self._data.alert.get('kind'))
        else:
            self._state = False
