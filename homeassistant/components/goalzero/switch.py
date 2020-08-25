"""Support for Goal Zero Yeti."""

import logging

from requests import post, get, exceptions
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_HOST, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.matches_regex(
            r"\A(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2 \
            [0-4][0-9]|[01]?[0-9][0-9]?)\Z"
        ),
        vol.Optional(CONF_NAME, default="Yeti"): cv.string,
    }
)

header = {
    "Content-Type": "application/json",
    "User-Agent": "YetiApp/1340 CFNetwork/1125.2 Darwin/19.4.0",
    "Connection": "keep-alive",
    "Accept": "application/json",
    "Accept-Language": "en-us",
    "Content-Length": "19",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the aREST switches."""

    name = config[CONF_NAME]
    host = config[CONF_HOST]

    try:
        response = get("http://" + host + "/state", timeout=10).json()
    except exceptions.MissingSchema:
        _LOGGER.error("Missing host or schema in configuration")
        return False
    except exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s", host)
        return False
    dev = []
    for variable in response:
        if variable in ["v12PortStatus", "usbPortStatus", "acPortStatus"]:
            dev.append(YetiSwitch(host, variable, name))

    add_entities(dev)


class YetiSwitch(ToggleEntity):
    """Representation of a Yeti switch."""

    def __init__(self, host, variable, client_name):
        """Initialize the switch."""
        self._name = [variable][0]
        self._host = host
        self.client_name = client_name
        self._state = STATE_OFF
        self._available = False
        self._variable = variable

    @property
    def name(self):
        """Return the name of the switch."""
        return f"{self.client_name} {self._name}"

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state == STATE_ON

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self._available

    def turn_on(self, **kwargs):
        """Turn the device on."""
        try:
            response = post(
                "http://" + self._host + "/state",
                json={self._variable: 1},
                headers=header,
                verify=False,
                timeout=10,
            ).json()
            self.data = response
            self._available = True
        except exceptions.MissingSchema:
            _LOGGER.error("Missing host or schema in configuration")
            self._available = False
            return False
        except exceptions.ConnectionError:
            _LOGGER.error("No route to device at %s", self._host)
            self._available = False
            return False

    def turn_off(self, **kwargs):
        """Turn the device off."""
        try:
            response = post(
                "http://" + self._host + "/state",
                json={self._variable: 0},
                headers=header,
                verify=False,
                timeout=10,
            ).json()
            self.data = response
            self._available = True
        except exceptions.MissingSchema:
            _LOGGER.error("Missing host or schema in configuration")
            self._available = False
            return False
        except exceptions.ConnectionError:
            _LOGGER.error("No route to device at %s", self._host)
            self._available = False
            return False

    def update(self):
        """Get the latest data from deluge and updates the state."""

        try:
            headers = {}

            response = get(
                "http://" + self._host + "/state", headers=headers, timeout=10
            ).json()
            self.data = response
            self._available = True
        except exceptions.MissingSchema:
            _LOGGER.error("Missing host or schema in configuration")
            self._available = False
            return False
        except exceptions.ConnectionError:
            _LOGGER.error("No route to device at %s", self._host)
            self._available = False
            return False

        for variable in response:
            if variable == self._variable:
                if self.data[variable] == 1:
                    self._state = STATE_ON
                else:
                    self._state = STATE_OFF
