"""
Allows to configure a switch using Synology Home Mode.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.synology_homemode/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_USERNAME, CONF_PASSWORD,
    CONF_URL)
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Home Mode"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_URL): cv.string,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Synology Home Mode switch."""
    _url = config.get(CONF_URL)
    _username = config.get(CONF_USERNAME)
    _password = config.get(CONF_PASSWORD)
    add_devices([
        SynologyHomeModeSwitch(DEFAULT_NAME, _url, _username, _password)])


class SynologyHomeModeSwitch(ToggleEntity):
    """Representation of Synology Home Mode Switch."""

    def __init__(self, name, host, username, password):
        """Initialize the switch."""
        self._name = name
        self._sid = ""
        self._host = host
        self._username = username
        self._password = password
        self._state = None
        self._login()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return True

    def update(self):
        self._get_info()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._state = True
        self._set_state("true")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._state = False
        self._set_state("false")

    def _login(self):
        """Login request"""
        try:
            url = '{0}/webapi/auth.cgi?api=SYNO.API.Auth&method=Login' + \
                '&version=3' + \
                '&account={1}&passwd={2}&session=SurveillanceStation' + \
                '&format=sid'

            url = url.format(self._host, self._username, self._password)
            res = requests.get(url, data={}, timeout=15).json()

            if res['success'] is True:
                self._sid = res['data']['sid']
                return True
            else:
                return False
        except (requests.exceptions.RequestException, ValueError):
            _LOGGER.exception("Error when initializing SurveillanceStation")
            return False

    def _get_info(self):
        """"Get info of Homemode"""
        try:
            url = '{0}/webapi/entry.cgi?' + \
                'api=SYNO.SurveillanceStation.HomeMode' + \
                '&version=1&method=GetInfo' + \
                '&_sid={1}'

            url = url.format(self._host, self._sid)

            res = requests.get(url, data={}, timeout=15).json()

            self._state = res['data']['on']
        except (requests.exceptions.RequestException, ValueError):
            self._state = False

    def _set_state(self, mode):
        """"Set state of Homemode"""
        try:
            url = '{0}/webapi/entry.cgi?' + \
                'api=SYNO.SurveillanceStation.HomeMode' + \
                '&version=1&method=Switch&on={1}' + \
                '&_sid={2}'

            url = url.format(self._host, mode, self._sid)
            requests.get(url, data={}, timeout=15).json()
        except (requests.exceptions.RequestException, ValueError):
            self._state = False
