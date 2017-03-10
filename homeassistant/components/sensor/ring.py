"""
This component provides HA sensor support for Ring Door Bell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ring/
"""
import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS, CONF_SCAN_INTERVAL,
    CONF_USERNAME, CONF_PASSWORD, STATE_UNKNOWN,
    ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
import homeassistant.loader as loader

from requests.exceptions import HTTPError, ConnectTimeout

REQUIREMENTS = ['ring_doorbell==0.1.1']

_LOGGER = logging.getLogger(__name__)

NOTIFICATION_ID = 'ring_notification'
NOTIFICATION_TITLE = 'Ring Sensor Setup'

DEFAULT_ENTITY_NAMESPACE = 'ring'
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

CONF_ATTRIBUTION = "Data provided by Ring.com"

# Sensor types: Name, category, units, icon
SENSOR_TYPES = {
    'battery': ['Battery', ['doorbell'], '%', 'battery-50'],
    'last_activity': ['Last Activity', ['doorbell'], None, 'history'],
    'volume': ['Volume', ['chime', 'doorbell'], None, 'bell-ring'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1)),
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a Ring device."""
    from ring_doorbell import Ring

    ring = Ring(config.get(CONF_USERNAME), config.get(CONF_PASSWORD))

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
        for device in ring.chimes:
            if 'chime' in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingSensor(hass,
                                          device,
                                          sensor_type))

        for device in ring.doorbells:
            if 'doorbell' in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingSensor(hass,
                                          device,
                                          sensor_type))

    add_devices(sensors, True)
    return True


class RingSensor(Entity):
    """A sensor implementation for Ring device."""

    def __init__(self, hass, data, sensor_type):
        """Initialize a sensor for Ring device."""
        super(RingSensor, self).__init__()
        self._sensor_type = sensor_type
        self._data = data
        self._extra = None
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[3])
        self._name = "{0} {1}".format(self._data.name,
                                      SENSOR_TYPES.get(self._sensor_type)[0])
        self._state = STATE_UNKNOWN
        self._tz = str(hass.config.time_zone)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
        attrs['device_id'] = self._data.id
        attrs['firmware'] = self._data.firmware
        attrs['kind'] = self._data.kind
        attrs['timezone'] = self._data.timezone
        attrs['type'] = self._data.family

        if self._extra and self._sensor_type == 'last_activity':
            attrs['created_at'] = self._extra['created_at']
            attrs['answered'] = self._extra['answered']
            attrs['recording_status'] = self._extra['recording']['status']
            attrs['category'] = self._extra['kind']

        return attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[2]

    def update(self):
        """Get the latest data and updates the state."""
        self._data.update()

        if self._sensor_type == 'volume':
            self._state = self._data.volume

        if self._sensor_type == 'battery':
            self._state = self._data.battery_life

        if self._sensor_type == 'last_activity':
            self._extra = self._data.history(limit=1, timezone=self._tz)[0]
            created_at = self._extra['created_at']
            self._state = '{0:0>2}:{1:0>2}'.format(created_at.hour,
                                                   created_at.minute)
