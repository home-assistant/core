"""
Support for Zabbix Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.zabbix/
"""
import logging

import voluptuous as vol

from homeassistant.components import zabbix
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zabbix']

_CONF_TRIGGERS = 'triggers'
_CONF_HOSTIDS = 'hostids'
_CONF_INDIVIDUAL = 'individual'

_ZABBIX_ID_LIST_SCHEMA = vol.Schema([int])
_ZABBIX_TRIGGER_SCHEMA = vol.Schema({
    vol.Optional(_CONF_HOSTIDS, default=[]): _ZABBIX_ID_LIST_SCHEMA,
    vol.Optional(_CONF_INDIVIDUAL, default=False): cv.boolean,
    vol.Optional(CONF_NAME): cv.string,
})

# SCAN_INTERVAL = 30
#
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(_CONF_TRIGGERS): vol.Any(_ZABBIX_TRIGGER_SCHEMA, None)
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Zabbix sensor platform."""
    sensors = []

    zapi = hass.data[zabbix.DOMAIN]
    if not zapi:
        _LOGGER.error("zapi is None. Zabbix component hasn't been loaded?")
        return False

    _LOGGER.info("Connected to Zabbix API Version %s", zapi.api_version())

    trigger_conf = config.get(_CONF_TRIGGERS)
    # The following code seems overly complex. Need to think about this...
    if trigger_conf:
        hostids = trigger_conf.get(_CONF_HOSTIDS)
        individual = trigger_conf.get(_CONF_INDIVIDUAL)
        name = trigger_conf.get(CONF_NAME)

        if individual:
            # Individual sensor per host
            if not hostids:
                # We need hostids
                _LOGGER.error("If using 'individual', must specify hostids")
                return False

            for hostid in hostids:
                _LOGGER.debug("Creating Zabbix Sensor: %s", str(hostid))
                sensor = ZabbixSingleHostTriggerCountSensor(
                    zapi, [hostid], name)
                sensors.append(sensor)
        else:
            if not hostids:
                # Single sensor that provides the total count of triggers.
                _LOGGER.debug("Creating Zabbix Sensor")
                sensor = ZabbixTriggerCountSensor(zapi, name)
            else:
                # Single sensor that sums total issues for all hosts
                _LOGGER.debug("Creating Zabbix Sensor group: %s", str(hostids))
                sensor = ZabbixMultipleHostTriggerCountSensor(
                    zapi, hostids, name)
            sensors.append(sensor)
    else:
        # Single sensor that provides the total count of triggers.
        _LOGGER.debug("Creating Zabbix Sensor")
        sensor = ZabbixTriggerCountSensor(zapi)
        sensors.append(sensor)

    add_entities(sensors)


class ZabbixTriggerCountSensor(Entity):
    """Get the active trigger count for all Zabbix monitored hosts."""

    def __init__(self, zApi, name="Zabbix"):
        """Initialize Zabbix sensor."""
        self._name = name
        self._zapi = zApi
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

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return 'issues'

    def _call_zabbix_api(self):
        return self._zapi.trigger.get(
            output="extend", only_true=1, monitored=1, filter={"value": 1})

    def update(self):
        """Update the sensor."""
        _LOGGER.debug("Updating ZabbixTriggerCountSensor: %s", str(self._name))
        triggers = self._call_zabbix_api()
        self._state = len(triggers)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._attributes


class ZabbixSingleHostTriggerCountSensor(ZabbixTriggerCountSensor):
    """Get the active trigger count for a single Zabbix monitored host."""

    def __init__(self, zApi, hostid, name=None):
        """Initialize Zabbix sensor."""
        super().__init__(zApi, name)
        self._hostid = hostid
        if not name:
            self._name = self._zapi.host.get(
                hostids=self._hostid, output="extend")[0]["name"]

        self._attributes["Host ID"] = self._hostid

    def _call_zabbix_api(self):
        return self._zapi.trigger.get(
            hostids=self._hostid, output="extend", only_true=1, monitored=1,
            filter={"value": 1})


class ZabbixMultipleHostTriggerCountSensor(ZabbixTriggerCountSensor):
    """Get the active trigger count for specified Zabbix monitored hosts."""

    def __init__(self, zApi, hostids, name=None):
        """Initialize Zabbix sensor."""
        super().__init__(zApi, name)
        self._hostids = hostids
        if not name:
            host_names = self._zapi.host.get(
                hostids=self._hostids, output="extend")
            self._name = " ".join(name["name"] for name in host_names)
        self._attributes["Host IDs"] = self._hostids

    def _call_zabbix_api(self):
        return self._zapi.trigger.get(
            hostids=self._hostids, output="extend", only_true=1,
            monitored=1, filter={"value": 1})
