"""
homeassistant.components.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tellduslive Component

This component adds support for the Telldus Live service.
Telldus Live is the online service used with Tellstick Net devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tellduslive/

You will need to setup developer access to your Telldus Net device and
create API keys on the Telldus website. 
API keys can be aquired from https://api.telldus.com/keys/index

Tellstick Net devices can be auto discovered using the method described in:
https://developer.telldus.com/doxygen/html/TellStickNet.html

It might be possible to communicate with the Tellstick Net device
directly, bypassing the Tellstick Live service.
This however is poorly documented and yet not fully supported (?) according to
http://developer.telldus.se/ticket/114 and 
https://developer.telldus.com/doxygen/html/TellStickNet.html

API requests to certain methods, as described in https://api.telldus.com/explore/sensor/info 
are limited to one request every 10 minutes
"""

from datetime import timedelta
import logging
import os

from homeassistant.loader import get_component
from homeassistant import bootstrap
from homeassistant.util import Throttle
from homeassistant.helpers import validate_config
from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED, CONF_API_KEY)

DOMAIN = "tellduslive"
DISCOVER_SWITCHES = "tellduslive.switches"
DISCOVER_SENSORS = "tellduslive.sensors"

CONF_PUBLIC_KEY = "public_key"
CONF_PRIVATE_KEY = "private_key"
CONF_TOKEN = "token"
CONF_TOKEN_SECRET = "token_secret"

REQUIREMENTS = ['tellive-py==0.5.2']
_LOGGER = logging.getLogger(__name__)

NETWORK = None

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=600)

class TelldusLiveData(object):
    """ Gets the latest data and update the states. """

    def __init__(self, config):
        public_key = config[DOMAIN].get(CONF_PUBLIC_KEY)
        private_key = config[DOMAIN].get(CONF_PRIVATE_KEY)
        token = config[DOMAIN].get(CONF_TOKEN)
        token_secret = config[DOMAIN].get(CONF_TOKEN_SECRET)

        from tellive.client import LiveClient
        self.sensors = []
        self.client = LiveClient(public_key = public_key,
                                 private_key = private_key,
                                 access_token = token,
                                 access_secret = token_secret)
        

    def request(self, what, params={}):
        return self.client.request(what, params)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_sensors(self):
        """ Get the latest data from telldus live """
        _LOGGER.info("Updating sensors for real")
        params = { "includeValues": 1,
                   "includeScale": 1 }
        response = self.request("sensors/list", params)
        return response["sensor"]

    def get_sensors(self):
        _LOGGER.info("Maybe updating sensors")
        updated_sensors = self._update_sensors()
        if updated_sensors is None:
            _LOGGER.info("Not actually updating sensors yet")
        else:
            _LOGGER.info("tellduslive data updated successfully.")
            self.sensors = updated_sensors
        return self.sensors

    def get_switches(self):
        response = self.request("devices/list")
        return response["device"]


def setup(hass, config):
    """ Setup the tellduslive component """

    # later: aquire an app key and authenticate using username + password
    if not validate_config(config, {DOMAIN: [ CONF_PUBLIC_KEY, 
                                              CONF_PRIVATE_KEY, 
                                              CONF_TOKEN, 
                                              CONF_TOKEN_SECRET ]}, _LOGGER):
        _LOGGER.error(
            "Configuration Error: "
            "Please make sure you have configured your keys "
            "that can be aquired from https://api.telldus.com/keys/index")
        return False

    global NETWORK
    NETWORK = TelldusLiveData(config)
    
    for component_name, discovery_type in (
            ('switch', DISCOVER_SWITCHES),
            ('sensor',  DISCOVER_SENSORS)):
        component = get_component(component_name)
        bootstrap.setup_component(hass, component.DOMAIN, config)
        _LOGGER.debug("firing discovery event: " + discovery_type)
        hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
            ATTR_SERVICE: discovery_type,
            ATTR_DISCOVERED: {}
        })
    return True
