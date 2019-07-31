"""Suppoort for Mikrotik binary sensors."""
from datetime import timedelta
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDevice)
from homeassistant.const import CONF_HOST, CONF_BINARY_SENSORS
from . import (MIKROTIK, CLIENT, BINARY_SENSORS,
               BINARY_SENSOR_NETWATCH)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a binary sensor for a Mikrotik device."""
    if discovery_info is None:
        return
    host = discovery_info[CONF_HOST]
    client = hass.data[CLIENT]
    entities = []
    binary_sensors = hass.data[MIKROTIK][host][CONF_BINARY_SENSORS]
    hass.data[MIKROTIK][host][CONF_BINARY_SENSORS] = {}
    for sensor_type in discovery_info[CONF_BINARY_SENSORS]:
        hass.data[MIKROTIK][host][sensor_type] = {}
        sensor_name = ''
        if sensor_type == BINARY_SENSOR_NETWATCH:
            await client.update_binary_sensor(host, sensor_type)
            count = int(hass.data[MIKROTIK][host][sensor_type]['count'])
            for index in range(count):
                binary_sensor = binary_sensors[sensor_type][index]['attrib']
                if 'comment' in binary_sensor:
                    sensor_name = binary_sensor['comment']
                else:
                    sensor_name = binary_sensor['host']
                entities.append(MikrotikBinarySensor(
                    hass, client, host, sensor_name, sensor_type, index))
        else:
            entities.append(MikrotikBinarySensor(
                hass, client, host, sensor_name, sensor_type))

    async_add_entities(entities, True)


class MikrotikBinarySensor(BinarySensorDevice):
    """Binary sensor for Mikrotik device."""

    def __init__(self, hass, client, host, sensor_name, sensor_type, index=0):
        """Initialize entity."""
        self._state = None
        self._attrs = None
        self.hass = hass
        self._client = client
        self._host = host
        self._index = index
        self._sensor_type = sensor_type
        self._device_class = BINARY_SENSORS[sensor_type][1]
        self._host_name = hass.data[MIKROTIK][host].get('name')
        self._name = '{} {} {}'.format(
            self._host_name, BINARY_SENSORS[sensor_type][0], sensor_name)
        _LOGGER.debug('[%s] init entity (%d) %s' % (host, index, self._name))

    @property
    def name(self):
        """Return entity name."""
        return self._name

    @property
    def device_class(self):
        """Return device class."""
        return self._device_class

    @property
    def is_on(self):
        """Return if the binary sensor is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    async def async_update(self, now=None):
        """Update entity."""
        if self._index == 0:
            await self._client.update_binary_sensor(
                self._host, self._sensor_type, self._index)
        binary_sensor = self.hass.data[MIKROTIK][
            self._host][CONF_BINARY_SENSORS][
            self._sensor_type][self._index]
        self._state = bool(binary_sensor.get('state'))
        self._attrs = binary_sensor.get('attrib')
