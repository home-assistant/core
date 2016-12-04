"""
Support for Zabbix Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zabbix/
"""
import logging

from homeassistant.helpers.entity import Entity
import homeassistant.components.zabbix as zabbix
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zabbix']

_HOSTID = "hostid"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(_HOSTID): cv.string,
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Zabbix sensor platform."""
    sensors = []

    _LOGGER.info("Creating Zabbix Sensor")
    _LOGGER.info("Connected to Zabbix API Version %s" % zabbix.ZAPI.api_version())

    sensor = ZabbixSensor(config.get(_HOSTID))
    sensors.append(sensor)

    add_devices(sensors)

class ZabbixSensor(Entity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, id):
        """Initiate monitor sensor."""
        self._id = id
        self._name = zabbix.ZAPI.host.get(hostids=self._id, output="extend")[0]["name"]
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} Issues'.format(self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor."""
        triggers = zabbix.ZAPI.trigger.get(hostids=self._id, output="extend", only_true=1, filter={"value": 1})
        self._state = len(triggers)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['Host Id'] = self._id
        return attr

