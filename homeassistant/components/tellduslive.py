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

        from tellive.client import LiveClient
        from tellive.live import TelldusLive

        self._sensors = []
        self._switches = []

        self._client = LiveClient(public_key=public_key,
                                  private_key=private_key,
                                  access_token=token,
                                  access_secret=token_secret)
        self._api = TelldusLive(self._client)

    def update(self, hass, config):
        """ Send discovery event if component not yet discovered """
        self._update_sensors()
        self._update_switches()
        for component_name, found_devices, discovery_type in \
            (('sensor', self._sensors, DISCOVER_SENSORS),
             ('switch', self._switches, DISCOVER_SWITCHES)):
            if len(found_devices):
                component = get_component(component_name)
                bootstrap.setup_component(hass, component.DOMAIN, config)
                hass.bus.fire(EVENT_PLATFORM_DISCOVERED,
                              {ATTR_SERVICE: discovery_type,
                               ATTR_DISCOVERED: {}})

    def _request(self, what, **params):
        """ Sends a request to the tellstick live API """

        from tellive.live import const

        supported_methods = const.TELLSTICK_TURNON \
            | const.TELLSTICK_TURNOFF \
            | const.TELLSTICK_TOGGLE

        default_params = {'supportedMethods': supported_methods,
                          "includeValues": 1,
                          "includeScale": 1}

        params.update(default_params)

        # room for improvement: the telllive library doesn't seem to
        # re-use sessions, instead it opens a new session for each request
        # this needs to be fixed
        response = self._client.request(what, params)
        return response

    def check_request(self, what, **params):
        """ Make request, check result if successful """
        response = self._request(what, **params)
        return response['status'] == "success"

    def validate_session(self):
        """ Make a dummy request to see if the session is valid """
        try:
            response = self._request("user/profile")
            return 'email' in response
        except RuntimeError:
            return False

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_sensors(self):
        """ Get the latest sensor data from Telldus Live """
        _LOGGER.info("Updating sensors from Telldus Live")
        self._sensors = self._request("sensors/list")["sensor"]

    def _update_switches(self):
        """ Get the configured switches from Telldus Live"""
        _LOGGER.info("Updating switches from Telldus Live")
        self._switches = self._request("devices/list")["device"]
        # filter out any group of switches
        self._switches = [switch for switch in self._switches
                          if switch["type"] == "device"]

    def get_sensors(self):
        """ Get the configured sensors """
        self._update_sensors()
        return self._sensors

    def get_switches(self):
        """ Get the configured switches """
        self._update_switches()
        return self._switches

    def get_sensor_value(self, sensor_id, sensor_name):
        """ Get the latest (possibly cached) sensor value """
        self._update_sensors()
        for component in self._sensors:
            if component["id"] == sensor_id:
                for sensor in component["data"]:
                    if sensor["name"] == sensor_name:
                        return (sensor["value"],
                                component["battery"],
                                component["lastUpdated"])

    def get_switch_state(self, switch_id):
        """ returns state of switch. """
        _LOGGER.info("Updating switch state from Telldus Live")
        response = self._request("device/info", id=switch_id)["state"]
        return int(response)

    def turn_switch_on(self, switch_id):
        """ turn switch off """
        return self.check_request("device/turnOn", id=switch_id)

    def turn_switch_off(self, switch_id):
        """ turn switch on """
        return self.check_request("device/turnOff", id=switch_id)


def setup(hass, config):
    """ Setup the tellduslive component """

    # fixme: aquire app key and provide authentication
    # using username + password
    if not validate_config(config,
                           {DOMAIN: [CONF_PUBLIC_KEY,
                                     CONF_PRIVATE_KEY,
                                     CONF_TOKEN,
                                     CONF_TOKEN_SECRET]},
                           _LOGGER):
        _LOGGER.error(
            "Configuration Error: "
            "Please make sure you have configured your keys "
            "that can be aquired from https://api.telldus.com/keys/index")
        return False

    global NETWORK
    NETWORK = TelldusLiveData(hass, config)

    if not NETWORK.validate_session():
        _LOGGER.error(
            "Authentication Error: "
            "Please make sure you have configured your keys "
            "that can be aquired from https://api.telldus.com/keys/index")
        return False

    NETWORK.update(hass, config)

    return True
