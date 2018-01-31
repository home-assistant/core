"""
Allows to configure a switch using RPi GPIO.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.synology_homemode/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
    CONF_URL, CONF_TIMEOUT)
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['']

DEFAULT_NAME = "Home Mode"
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Raspberry PI GPIO devices."""
    _timeout = config.get(CONF_TIMEOUT)
    _url = config.get(CONF_URL)
    _username = config.get(CONF_USERNAME)
    _password = config.get(CONF_PASSWORD)

    try:

        self._login(_url, _username, _password)

    except (requests.exceptions.RequestException, ValueError):
        _LOGGER.exception("Error when initializing SurveillanceStation")
        return False
    
    add_devices(SynologyHomeModeSwitch(DEFAULT_NAME, ))

def _login(host, username, password):
    """Login request"""
    url = '{}/webapi/auth.cgi?api=SYNO.API.Auth&method=Login&version=3' + \
          '&account={}&passwd={}!&session=SurveillanceStation' + \
          '&format=sid'.format(host, username, password)

    res = requests.post(url, data={}, timeout=5)

"""
pi@raspberrypi ~ $ curl -L "http://192.168.1.101:5000/webapi/auth.cgi?api=SYNO.API.Auth&method=Login&version=3&account=XXXXXXX&passwd=XXXXXXXX&session=SurveillanceStation&format=sid"
{"data":{"sid":"Gj.tXLURyrKZg1510MPN674502"},"success":true}


Home Mode on

pi@raspberrypi ~ $ curl -L "http://192.168.1.101:5000/webapi/entry.cgi?api=SYNO.SurveillanceStation.HomeMode&version=1&method=Switch&on=true&_sid=Gj.tXLURyrKZg1510MPN674502"


Home Mode OFF

{"success":true}pi@raspberrypi ~ $ curl -L "http://192.168.1.101:5000/webapi/entry.cgi?api=SYNO.SurveillanceStation.HomeMode&version=1&method=Switch&on=false&_sid=Gj.tXLURyrKZg1510MPN674502"
"""


class SynologyHomeModeSwitch(ToggleEntity):
    """Representation of a  Raspberry Pi GPIO."""

    def __init__(self, name):
        """Initialize the pin."""
        self._name = name or DEFAULT_NAME
        
    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._state = False
        self.schedule_update_ha_state()
