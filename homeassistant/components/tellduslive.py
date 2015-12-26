"""
homeassistant.components.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tellduslive Component

This component adds support for the Telldus Live service.
Telldus Live is the online service used with Tellstick Net devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tellduslive/

Developer access to the Telldus Live service is neccessary
API keys can be aquired from https://api.telldus.com/keys/index

Tellstick Net devices can be auto discovered using the method described in:
https://developer.telldus.com/doxygen/html/TellStickNet.html

It might be possible to communicate with the Tellstick Net device
directly, bypassing the Tellstick Live service.
This however is poorly documented and yet not fully supported (?) according to
http://developer.telldus.se/ticket/114 and
https://developer.telldus.com/doxygen/html/TellStickNet.html

API requests to certain methods, as described in
https://api.telldus.com/explore/sensor/info
are limited to one request every 10 minutes

"""

from datetime import timedelta
import logging

from homeassistant.loader import get_component
from homeassistant import bootstrap
from homeassistant.util import Throttle
from homeassistant.helpers import validate_config
from homeassistant.const import (
    EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED)


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

    def __init__(self, hass, config):

        public_key = config[DOMAIN].get(CONF_PUBLIC_KEY)
        private_key = config[DOMAIN].get(CONF_PRIVATE_KEY)
        token = config[DOMAIN].get(CONF_TOKEN)
        token_secret = config[DOMAIN].get(CONF_TOKEN_SECRET)

        self._hass = hass
        self._config = config

        from tellive.client import LiveClient
        from tellive.live import TelldusLive

        self._sensors  = []
        self._switches = []

        self._client = LiveClient(public_key=public_key,
                                  private_key=private_key,
                                  access_token=token,
                                  access_secret=token_secret)
        self._api = TelldusLive(self._client)
        
        self._update()
        _LOGGER.info("got %d switches" % len(self._switches))
        _LOGGER.info("got %d sensors" % len(self._sensors))

    def _request(self, what, params):
        """ Sends a request to the tellstick live API """
        return self._client.request(what, params)

    def _setup_component(self, name, discovery_type):
        """ Send discovery event if component not yet discovered """
        component = get_component(name)
        if component.DOMAIN not in self._hass.config.components:
            bootstrap.setup_component(self._hass, component.DOMAIN, self._config)
            _LOGGER.debug("firing discovery event: " + discovery_type)
            self._hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: discovery_type,
                ATTR_DISCOVERED: {}
            })
        # fixme: also discover new sensors/switches as they are plugged in?

    def check_request(self, what, params):
        """ Make request, check if successful """
        return self._request(what, params) == "success"

    def _update_switches(self):
        _LOGGER.info("Updating switches from Telldus Live")
        from tellcore.constants import (
            TELLSTICK_TURNON, TELLSTICK_TURNOFF, TELLSTICK_TOGGLE)
        
        SUPPORTED_METHODS = TELLSTICK_TURNON \
                            | TELLSTICK_TURNOFF \
                            | TELLSTICK_TOGGLE
        
        params = {'supportedMethods': SUPPORTED_METHODS}

        self._switches = self._request("devices/list", params)["device"]

        # filter out any group of switches
        self._switches = [ switch for switch in self._switches if switch["type"] == "device" ]

        if len(self._switches):
            self._setup_component('switch', DISCOVER_SWITCHES)
        
    @Throttle(MIN_TIME_BETWEEN_UPDATES) # according to API documentation
    def _update_sensors(self):
        """ Get the latest data from Telldus Live """
        _LOGGER.info("Updating sensors from Telldus Live")

        params = {"includeValues": 1,
                  "includeScale": 1}

        self._sensors  = self._request("sensors/list", params)["sensor"]

        if len(self._sensors):
            self._setup_component('sensor', DISCOVER_SENSORS)

    def get_sensors(self):
        """ Get the latest (possibly cached) sensor values """
        self._update_sensors()
        return self._sensors

    def get_switches(self):
        """ Get the configured switches """
        self._update_switches()
        return self._switches
        
    def _update(self):
        self._update_sensors()
        self._update_switches()

def setup(hass, config):
    """ Setup the tellduslive component """

    # fixme: aquire app key and provide authentication using username + password
    if not validate_config(config, {DOMAIN: [CONF_PUBLIC_KEY,
                                             CONF_PRIVATE_KEY,
                                             CONF_TOKEN,
                                             CONF_TOKEN_SECRET]}, _LOGGER):
        _LOGGER.error(
            "Configuration Error: "
            "Please make sure you have configured your keys "
            "that can be aquired from https://api.telldus.com/keys/index")
        return False

    # fixme: validate key?

    global NETWORK
    NETWORK = TelldusLiveData(hass, config)

    return True
