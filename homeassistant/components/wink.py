"""
Support for Wink hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wink/
"""
import logging
import json

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import CONF_ACCESS_TOKEN, ATTR_BATTERY_LEVEL, \
                                CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-wink==0.8.0', 'pubnub==3.8.2']

_LOGGER = logging.getLogger(__name__)

CHANNELS = []

DOMAIN = 'wink'

SUBSCRIPTION_HANDLER = None
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_USER_AGENT = 'user_agent'
CONF_OATH = 'oath'
CONF_DEFINED_BOTH_MSG = 'Remove access token to use oath2.'
CONF_MISSING_OATH_MSG = 'Missing oath2 credentials.'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_EMAIL, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_PASSWORD, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_ID, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_SECRET, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Exclusive(CONF_EMAIL, CONF_OATH,
                      msg=CONF_DEFINED_BOTH_MSG): cv.string,
        vol.Exclusive(CONF_ACCESS_TOKEN, CONF_OATH,
                      msg=CONF_DEFINED_BOTH_MSG): cv.string,
        vol.Optional(CONF_USER_AGENT, default=None): cv.string
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the Wink component."""
    import pywink

    user_agent = config[DOMAIN][CONF_USER_AGENT]

    if user_agent:
        pywink.set_user_agent(user_agent)

    from pubnub import Pubnub
    access_token = config[DOMAIN].get(CONF_ACCESS_TOKEN)

    if access_token:
        pywink.set_bearer_token(access_token)
    else:
        email = config[DOMAIN][CONF_EMAIL]
        password = config[DOMAIN][CONF_PASSWORD]
        client_id = config[DOMAIN]['client_id']
        client_secret = config[DOMAIN]['client_secret']
        pywink.set_wink_credentials(email, password, client_id,
                                    client_secret)

    global SUBSCRIPTION_HANDLER
    SUBSCRIPTION_HANDLER = Pubnub(
        'N/A', pywink.get_subscription_key(), ssl_on=True)
    SUBSCRIPTION_HANDLER.set_heartbeat(120)

    # Load components for the devices in Wink that we support
    for component_name, func_exists in (
            ('light', pywink.get_bulbs),
            ('switch', lambda: pywink.get_switches or pywink.get_sirens or
             pywink.get_powerstrip_outlets),
            ('binary_sensor', pywink.get_sensors),
            ('sensor', lambda: pywink.get_sensors or pywink.get_eggtrays),
            ('lock', pywink.get_locks),
            ('cover', pywink.get_shades),
            ('cover', pywink.get_garage_doors)):

        if func_exists():
            discovery.load_platform(hass, component_name, DOMAIN, {}, config)

    return True


class WinkDevice(Entity):
    """Representation a base Wink device."""

    def __init__(self, wink):
        """Initialize the Wink device."""
        from pubnub import Pubnub
        self.wink = wink
        self._battery = self.wink.battery_level
        if self.wink.pubnub_channel in CHANNELS:
            pubnub = Pubnub('N/A', self.wink.pubnub_key, ssl_on=True)
            pubnub.set_heartbeat(120)
            pubnub.subscribe(self.wink.pubnub_channel,
                             self._pubnub_update,
                             error=self._pubnub_error)
        else:
            CHANNELS.append(self.wink.pubnub_channel)
            SUBSCRIPTION_HANDLER.subscribe(self.wink.pubnub_channel,
                                           self._pubnub_update,
                                           error=self._pubnub_error)

    def _pubnub_update(self, message, channel):
        self.wink.pubnub_update(json.loads(message))
        self.update_ha_state()

    def _pubnub_error(self, message):
        _LOGGER.error("Error on pubnub update for " + self.wink.name())

    @property
    def unique_id(self):
        """Return the ID of this Wink device."""
        return '{}.{}'.format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the device."""
        return self.wink.name()

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    def update(self):
        """Update state of the device."""
        self.wink.update_state()

    @property
    def should_poll(self):
        """Only poll if we are not subscribed to pubnub."""
        return self.wink.pubnub_channel is None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery_level,
            }

    @property
    def _battery_level(self):
        """Return the battery level."""
        return self.wink.battery_level * 100
