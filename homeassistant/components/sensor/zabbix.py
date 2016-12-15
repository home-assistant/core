"""
Support for Zabbix Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zabbix/
"""
import logging
import voluptuous as vol

from homeassistant.helpers.entity import Entity
import homeassistant.components.zabbix as zabbix
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zabbix']

_CONF_TRIGGERS = "triggers"
_CONF_HOSTIDS = "hostids"
_CONF_INDIVIDUAL = "individual"
_CONF_NAME = "name"

_ZABBIX_ID_LIST_SCHEMA = vol.Schema([int])
_ZABBIX_TRIGGER_SCHEMA = vol.Schema({
      vol.Optional(_CONF_HOSTIDS, default=[]): _ZABBIX_ID_LIST_SCHEMA,
      vol.Optional(_CONF_INDIVIDUAL, default=False): cv.boolean(True),
      vol.Optional(_CONF_NAME, default=None): cv.string,
})

SCAN_INTERVAL = 30

    # triggers:
    #   name: Test Name
    #   hostids: [10051]
    #   individual: true
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(_CONF_TRIGGERS, default={}): vol.Any(
        _ZABBIX_TRIGGER_SCHEMA, None)
})
# all(any(None, bool), default_to(True)),


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Zabbix sensor platform."""
    sensors = []

    _LOGGER.info("Connected to Zabbix API Version %s",
                 zabbix.ZAPI.api_version())

    hostids = config.get(_CONF_HOSTIDS)
    individual = config.get(_CONF_INDIVIDUAL)
    name = config.get(_CONF_NAME)

    if individual:
        # Individual sensor per host
        if not hostids:
            # We need hostids
            _LOGGER.error("If using 'individual', must specify hostids")
            return False

        for hostid in hostids:
            _LOGGER.debug("Creating Zabbix Sensor: " + str(hostid))
            sensor = ZabbixSingleHostTriggerCountSensor([hostid], name)
            sensors.append(sensor)
    else:
        if not hostids:
            # Single sensor that provides the total count of triggers.
            _LOGGER.debug("Creating Zabbix Sensor")
            sensor = ZabbixTriggerCountSensor(name)
        else:
            # Single sensor that sums total issues for all hosts
            _LOGGER.debug("Creating Zabbix Sensor for group: " + str(hostids))
            sensor = ZabbixMultipleHostTriggerCountSensor(hostids, name)
        sensors.append(sensor)

    add_devices(sensors)


class ZabbixTriggerCountSensor(Entity):
    """Get the active trigger count for all Zabbix monitored hosts."""

    def __init__(self, name):
        """Initiate Zabbix sensor."""
        self._name = "Zabbix"
        if name:
            self._name = name
        self._state = None
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _call_zabbix_api(self):
        return zabbix.ZAPI.trigger.get(output="extend",
                                       only_true=1,
                                       monitored=1,
                                       filter={"value": 1})

    def update(self):
        """Update the sensor."""
        _LOGGER.debug("Updating ZabbixTriggerCountSensor: " + str(self._name))
        triggers = self._call_zabbix_api()
        self._state = len(triggers)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes


class ZabbixSingleHostTriggerCountSensor(ZabbixTriggerCountSensor):
    """Get the active trigger count for a single Zabbix monitored host."""

    def __init__(self, hostid, name=None):
        """Initiate Zabbix sensor."""
        super().__init__(name)
        self._hostid = hostid
        if not name:
            self._name = zabbix.ZAPI.host.get(hostids=self._hostid,
                                              output="extend")[0]["name"]

        self._attributes["Host ID"] = self._hostid

    def _call_zabbix_api(self):
        return zabbix.ZAPI.trigger.get(hostids=self._hostid,
                                       output="extend",
                                       only_true=1,
                                       monitored=1,
                                       filter={"value": 1})


class ZabbixMultipleHostTriggerCountSensor(ZabbixTriggerCountSensor):
    """Get the active trigger count for specified Zabbix monitored hosts."""

    def __init__(self, hostids, name=None):
        """Initiate Zabbix sensor."""
        super().__init__(name)
        self._hostids = hostids
        if not name:
            host_names = zabbix.ZAPI.host.get(hostids=self._hostids,
                                              output="extend")
            self._name = " ".join(name["name"] for name in host_names)
        self._attributes["Host IDs"] = self._hostids

    def _call_zabbix_api(self):
        return zabbix.ZAPI.trigger.get(hostids=self._hostids,
                                       output="extend",
                                       only_true=1,
                                       monitored=1,
                                       filter={"value": 1})
