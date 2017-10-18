"""
This component provides HA sensor support for Ring Door Bell/Chimes.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ring/
"""
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.ring import (
    CONF_ATTRIBUTION, DEFAULT_ENTITY_NAMESPACE)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS,
    STATE_UNKNOWN, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level

DEPENDENCIES = ['ring']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# Sensor types: Name, category, units, icon, kind
SENSOR_TYPES = {
    'battery': ['Battery', ['doorbell'], '%', 'battery-50', None],
    'last_activity': ['Last Activity', ['doorbell'], None, 'history', None],
    'last_ding': ['Last Ding', ['doorbell'], None, 'history', 'ding'],
    'last_motion': ['Last Motion', ['doorbell'], None, 'history', 'motion'],
    'volume': ['Volume', ['chime', 'doorbell'], None, 'bell-ring', None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAMESPACE, default=DEFAULT_ENTITY_NAMESPACE):
        cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for a Ring device."""
    ring = hass.data.get('ring')

    sensors = []
    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        for device in ring.chimes:
            if 'chime' in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingSensor(hass, device, sensor_type))

        for device in ring.doorbells:
            if 'doorbell' in SENSOR_TYPES[sensor_type][1]:
                sensors.append(RingSensor(hass, device, sensor_type))

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
        self._kind = SENSOR_TYPES.get(self._sensor_type)[4]
        self._name = "{0} {1}".format(
            self._data.name, SENSOR_TYPES.get(self._sensor_type)[0])
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

        if self._extra and self._sensor_type.startswith('last_'):
            attrs['created_at'] = self._extra['created_at']
            attrs['answered'] = self._extra['answered']
            attrs['recording_status'] = self._extra['recording']['status']
            attrs['category'] = self._extra['kind']

        return attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._sensor_type == 'battery' and self._state is not STATE_UNKNOWN:
            return icon_for_battery_level(battery_level=int(self._state),
                                          charging=False)
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[2]

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.debug("Pulling data from %s sensor", self._name)

        self._data.update()

        if self._sensor_type == 'volume':
            self._state = self._data.volume

        if self._sensor_type == 'battery':
            self._state = self._data.battery_life

        if self._sensor_type.startswith('last_'):
            history = self._data.history(timezone=self._tz,
                                         kind=self._kind)
            if history:
                self._extra = history[0]
                created_at = self._extra['created_at']
                self._state = '{0:0>2}:{1:0>2}'.format(
                    created_at.hour, created_at.minute)
