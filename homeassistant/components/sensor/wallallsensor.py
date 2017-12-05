"""
All sensors  available on a wall all device
"""
from datetime import timedelta
import logging
import asyncio
import voluptuous as vol
from wallall import wallall
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS,CONF_HOST, CONF_PORT,
    STATE_UNKNOWN, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity


DOMAIN = 'wallalldevice'

REQUIREMENTS = ['wallall==0.7']
LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# Sensor types: Name, category, units, icon, kind
SENSOR_TYPES = {
    'battery': ['Battery', ['WallAllDevice'], '%', 'value', None],
    'light': ['Light Sensor', ['WallAllDevice'], 'Lx', 'value', None],
    'sound': ['Sound Sensor', ['WallAllDevice'], 'Ampl', 'value', None],
    'brightness': ['Brightness', ['WallAllDevice'], '%', 'value', None],
    'volume': ['Volume', ['WallAllDevice'], None, 'value', None],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS, default=[]):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
})

wllDevice = None

@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a sensor for a WallAll device."""

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    wllDevice = wallall.WallAllCtx("{0}:{1}".format(host, port))

    sensors = []

    for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
        sensors.append(WallAllSensor(hass, wllDevice, sensor_type))
    async_add_devices(sensors)
    return True

class WallAllSensor(Entity):
    """A sensor implementation for a device running WallAll."""

    def __init__(self, hass, data, sensor_type):
        """Initialize a sensor for WallAll device."""
        super(WallAllSensor, self).__init__()
        self._sensor_type = sensor_type
        self._data = data
        self._extra = None
        self._icon = 'mdi:{}'.format(SENSOR_TYPES.get(self._sensor_type)[3])
        self._kind = SENSOR_TYPES.get(self._sensor_type)[4]
        self._name = SENSOR_TYPES.get(self._sensor_type)[0]
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any.
        if self._sensor_type == 'battery' and self._state is not STATE_UNKNOWN:
            return icon_for_battery_level(battery_level=int(self._state),
                                          charging=False)
        """
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES.get(self._sensor_type)[2]


    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        self._state = yield from self.hass.async_add_job(self.doupdate)
        return self._state


    def doupdate(self):
        """Get the latest data and updates the state."""
        
        if self._sensor_type == 'battery':
              self._state = self._data.battery
        elif self._sensor_type == 'light':
              self._state = self._data.lightsensor
        elif self._sensor_type == 'brightness':
              self._state = self._data.brightness
        elif self._sensor_type == 'sound':
              self._state = self._data.soundsensor
        elif self._sensor_type == 'volume':
              self._state = self._data.volume
        else: self._state = STATE_UNKNOWN

        return self._state
