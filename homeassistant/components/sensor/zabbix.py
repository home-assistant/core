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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(_CONF_TRIGGERS): vol.Any(_ZABBIX_TRIGGER_SCHEMA, None)
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Zabbix sensor platform."""
    sensors = []

    zApi = hass.data[zabbix.DOMAIN]
    if not zApi:
        _LOGGER.error("zApi is None.  Zabbix component hasn't been loaded?")
        return False

    _LOGGER.info("Connected to Zabbix API Version %s",
                 zApi.api_version())

    trigger_conf = config.get(_CONF_TRIGGERS)
    # The following code seems overly complex.  Need to think about this...
    if trigger_conf:
        hostids = trigger_conf.get(_CONF_HOSTIDS)
        individual = trigger_conf.get(_CONF_INDIVIDUAL)
        name = trigger_conf.get(_CONF_NAME)

        if individual:
            # Individual sensor per host
            if not hostids:
                # We need hostids
                _LOGGER.error("If using 'individual', must specify hostids")
                return False

            for hostid in hostids:
                _LOGGER.debug("Creating Zabbix Sensor: " + str(hostid))
                sensor = ZabbixSingleHostTriggerCountSensor(zApi, [hostid], name)
                sensors.append(sensor)
        else:
            if not hostids:
                # Single sensor that provides the total count of triggers.
                _LOGGER.debug("Creating Zabbix Sensor")
                sensor = ZabbixTriggerCountSensor(zApi, name)
            else:
                # Single sensor that sums total issues for all hosts
                _LOGGER.debug("Creating Zabbix Sensor for group: " + str(hostids))
                sensor = ZabbixMultipleHostTriggerCountSensor(zApi, hostids, name)
            sensors.append(sensor)
    else:
        # Single sensor that provides the total count of triggers.
        _LOGGER.debug("Creating Zabbix Sensor")
        sensor = ZabbixTriggerCountSensor(zApi)
        sensors.append(sensor)

    add_devices(sensors)


class ZabbixTriggerCountSensor(Entity):
    """Get the active trigger count for all Zabbix monitored hosts."""

    def __init__(self, zApi, name="Zabbix"):
        """Initiate Zabbix sensor."""
        self._name = name
        self._zApi = zApi
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
        return self._zApi.trigger.get(output="extend",
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

    def __init__(self, zApi, hostid, name=None):
        """Initiate Zabbix sensor."""
        super().__init__(zApi, name)
        self._hostid = hostid
        if not name:
            self._name = self._zApi.host.get(hostids=self._hostid,
                                              output="extend")[0]["name"]

        self._attributes["Host ID"] = self._hostid

    def _call_zabbix_api(self):
        return self._zApi.trigger.get(hostids=self._hostid,
                                       output="extend",
                                       only_true=1,
                                       monitored=1,
                                       filter={"value": 1})


class ZabbixMultipleHostTriggerCountSensor(ZabbixTriggerCountSensor):
    """Get the active trigger count for specified Zabbix monitored hosts."""

    def __init__(self, zApi, hostids, name=None):
        """Initiate Zabbix sensor."""
        super().__init__(zApi, name)
        self._hostids = hostids
        if not name:
            host_names = self._zApi.host.get(hostids=self._hostids,
                                              output="extend")
            self._name = " ".join(name["name"] for name in host_names)
        self._attributes["Host IDs"] = self._hostids

    def _call_zabbix_api(self):
        return self._zApi.trigger.get(hostids=self._hostids,
                                       output="extend",
                                       only_true=1,
                                       monitored=1,
                                       filter={"value": 1})
