"""Mikrotik status sensors."""
from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_HOST
from .const import DOMAIN, CLIENT, SENSOR, SENSORS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the mikrotik sensors."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    client = hass.data[CLIENT][host]
    await client.api.update_info()
    async_add_entities(
        [MikrotikSensor(hass, client, host, sensor_type)
         for sensor_type in discovery_info['sensors']])


class MikrotikSensor(Entity):
    """Representation of a mikrotik sensor."""

    def __init__(self, hass, client, host, sensor_type):
        """Initialize the sensor."""
        self.hass = hass
        self._host = host
        self._sensor_type = sensor_type
        self._client = client
        self._available = True
        self._state = None
        self._attrs = {}
        self._name = '{} {}'.format(client.host_name, SENSORS[sensor_type][0])
        self._unit = SENSORS[sensor_type][1]
        self._icon = SENSORS[sensor_type][2]
        self._item = SENSORS[sensor_type][3]
        if SENSOR not in self.hass.data[DOMAIN][host]:
            self.hass.data[DOMAIN][host][SENSOR] = {}
        self.hass.data[DOMAIN][host][SENSOR][sensor_type] = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return the availability state."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    async def async_update(self, now=None):
        """Get the latest data and updates the state."""
        sensor_type = self._sensor_type
        await self._client.api.update_sensors(sensor_type)
        if not self._client.api.connected():
            return
        host = self._host
        data = self.hass.data[DOMAIN][host][SENSOR][sensor_type]
        if data is None:
            _LOGGER.error("Mikrotik no sensor data %s", self._name)
            self._available = False
            return
        self._available = True
        self._state = data.get('state')
        self._attrs = data.get('attrib')
