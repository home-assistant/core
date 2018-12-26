"""
Fritzbox (Guest) WiFi Switch

Support for switching Fritzbox (Guest) Wifi on and off.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.fritzbox_wifi/
"""
# pylint: disable=import-error

import logging
import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_NAME, CONF_USERNAME, CONF_PASSWORD)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['fritzconnection==0.6.5']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Guest Wifi'
DEFAULT_HOST = '169.254.1.1'
DEFAULT_PORT = 49000
DEFAULT_INTERFACE = 3


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional('interface', DEFAULT_INTERFACE): cv.positive_int
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fritzbox WiFi switch platform."""
    import fritzconnection as fc
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    interface = config.get('interface')

    conn = fc.FritzConnection(
        address=host,
        port=port,
        user=username,
        password=password
    )
    add_entities([FritzBoxWifiSwitch(conn, name, interface)], True)


class FritzBoxWifiSwitch(SwitchDevice):
    """The switch class for Fritzbox WiFi switches."""

    def __init__(self, conn, name, interface):
        """Init individual Fritzbox WiFi switches."""
        self._conn = conn
        self._name = name
        self._interface = interface
        self._state = None
        self._available = True
        self._info = None

    @property
    def name(self):
        """Return the name of the wifi switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        self._info = self._conn.call_action(
            'WLANConfiguration:{}'.format(self._interface), 'GetInfo')
        info = self._info.get('NewEnable')
        if info == '1':
            _LOGGER.info('Guest Wifi On')
            self._state = True
        elif info == '0':
            _LOGGER.info('Guest WiFi Off')
            self._state = False
        return self._state

    def turn_on(self, **kwargs):
        """Turning on guest Wifi"""
        self._conn.call_action(
            'WLANConfiguration:{}'.format(self._interface),
            'SetEnable', NewEnable=1)
        self._state = True

    def turn_off(self, **kwargs):
        """Turning off guest WiFI"""
        self._conn.call_action(
            'WLANConfiguration:{}'.format(self._interface),
            'SetEnable', NewEnable=0)
        self._state = False
