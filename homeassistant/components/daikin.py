"""
Platform for the Daikin AC.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/daikin/
"""
import logging
from datetime import timedelta
from socket import timeout

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.discovery import SERVICE_DAIKIN
from homeassistant.const import (
    CONF_HOSTS, CONF_ICON, CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_TYPE
)
from homeassistant.helpers import discovery
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import Throttle

REQUIREMENTS = ['pydaikin==0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'daikin'
HTTP_RESOURCES = ['aircon/get_sensor_info', 'aircon/get_control_info']

ATTR_TARGET_TEMPERATURE = 'target_temperature'
ATTR_INSIDE_TEMPERATURE = 'inside_temperature'
ATTR_OUTSIDE_TEMPERATURE = 'outside_temperature'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

COMPONENT_TYPES = ['climate', 'sensor']

SENSOR_TYPE_TEMPERATURE = 'temperature'

SENSOR_TYPES = {
    ATTR_INSIDE_TEMPERATURE: {
        CONF_NAME: 'Inside Temperature',
        CONF_ICON: 'mdi:thermometer',
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE
    },
    ATTR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: 'Outside Temperature',
        CONF_ICON: 'mdi:thermometer',
        CONF_TYPE: SENSOR_TYPE_TEMPERATURE
    }

}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(
            CONF_HOSTS, default=[]
        ): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(
            CONF_MONITORED_CONDITIONS,
            default=list(SENSOR_TYPES.keys())
        ): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Establish connection with Daikin."""
    def discovery_dispatch(service, discovery_info):
        """Dispatcher for Daikin discovery events."""
        host = discovery_info.get('ip')

        if daikin_api_setup(hass, host) is None:
            return

        for component in COMPONENT_TYPES:
            load_platform(hass, component, DOMAIN, discovery_info,
                          config)

    discovery.listen(hass, SERVICE_DAIKIN, discovery_dispatch)

    for host in config.get(DOMAIN, {}).get(CONF_HOSTS, []):
        if daikin_api_setup(hass, host) is None:
            continue

        discovery_info = {
            'ip': host,
            CONF_MONITORED_CONDITIONS:
                config[DOMAIN][CONF_MONITORED_CONDITIONS]
        }
        load_platform(hass, 'sensor', DOMAIN, discovery_info, config)

    return True


def daikin_api_setup(hass, host, name=None):
    """Create a Daikin instance only once."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    api = hass.data[DOMAIN].get(host)
    if api is None:
        from pydaikin import appliance

        try:
            device = appliance.Appliance(host)
        except timeout:
            _LOGGER.error("Connection to Daikin could not be established")
            return False

        if name is None:
            name = device.values['name']

        api = DaikinApi(device, name)

    return api


class DaikinApi(object):
    """Keep the Daikin instance in one place and centralize the update."""

    def __init__(self, device, name):
        """Initialize the Daikin Handle."""
        self.device = device
        self.name = name
        self.ip_address = device.ip

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, **kwargs):
        """Pull the latest data from Daikin."""
        try:
            for resource in HTTP_RESOURCES:
                self.device.values.update(
                    self.device.get_resource(resource)
                )
        except timeout:
            _LOGGER.warning(
                "Connection failed for %s", self.ip_address
            )
