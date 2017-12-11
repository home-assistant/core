"""
Platform for the Daikin AC.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/daikin/
"""
import logging
import time
from socket import timeout
from threading import Lock

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.discovery import SERVICE_DAIKIN
from homeassistant.helpers import discovery
from homeassistant.helpers.discovery import load_platform
from homeassistant.const import (
    CONF_HOSTS, CONF_ICON, CONF_NAME,
    CONF_MONITORED_CONDITIONS
)

REQUIREMENTS = ['pydaikin==0.4']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'daikin'
HTTP_RESOURCES = ['aircon/get_sensor_info', 'aircon/get_control_info']

ATTR_TARGET_TEMPERATURE = 'target_temperature'
ATTR_INSIDE_TEMPERATURE = 'inside_temperature'
ATTR_OUTSIDE_TEMPERATURE = 'outside_temperature'

# default scan interval in seconds
DEFAULT_SCAN_INTERVAL = 60

COMPONENT_TYPES = ['climate', 'sensor']

SENSOR_TYPES = {
    ATTR_INSIDE_TEMPERATURE: {
        CONF_NAME: 'Inside Temperature',
        CONF_ICON: 'mdi:thermometer'
    },
    ATTR_OUTSIDE_TEMPERATURE: {
        CONF_NAME: 'Outside Temperature',
        CONF_ICON: 'mdi:thermometer'
    }

}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOSTS, default=[]): vol.Schema([cv.string]),
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

    devices = []

    # Add static devices from the config file.
    devices.extend(
        (host, None)
        for host in config.get(DOMAIN, {}).get(CONF_HOSTS, [])
    )

    for host in devices:
        if daikin_api_setup(hass, host) is not None:
            discovery_info = {
                'ip': host,
                CONF_MONITORED_CONDITIONS:
                    config.get(DOMAIN, {}).get(CONF_MONITORED_CONDITIONS)
            }
            load_platform(hass, 'sensor', DOMAIN, discovery_info, config)

    return True


def daikin_api_setup(hass, host, name=None):
    """Create a Daikin instance only once."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    if hass.data[DOMAIN].get(host) is None:
        from pydaikin import appliance

        try:
            device = appliance.Appliance(host)
        except timeout:
            _LOGGER.error("Connection to Daikin could not be established")
            return False

        if name is None:
            name = device.values['name']

        hass.data[DOMAIN][host] = DaikinApi(device, name)

    return hass.data[DOMAIN][host]


class DaikinApi(object):
    """Keep the Daikin instance in one place and centralize the update."""

    def __init__(self, device, name):
        """Initialize the Daikin Handle."""
        self.device = device
        self.name = name
        self.ip_address = device.ip

        self.mutex = Lock()
        self._scan_interval = DEFAULT_SCAN_INTERVAL
        self._last_update = time.time()

    def update(self, force_refresh=False):
        """Pull the latest data from Daikin."""
        # Acquire mutex to prevent simultaneous update from multiple threads
        with self.mutex:
            # don't update too often
            if force_refresh or \
                    (time.time() - self._last_update) >= self._scan_interval:

                try:
                    for resource in HTTP_RESOURCES:
                        self.device.values.update(
                            self.device.get_resource(resource)
                        )
                except timeout:
                    _LOGGER.warning(
                        "Connection failed for %s, retying in %d seconds",
                        self.ip_address, self._scan_interval
                    )
                    return False

                self._last_update = time.time()
