"""The totalconnect component."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Total Connect'

DOMAIN = 'totalconnect'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

TOTALCONNECT_PLATFORMS = ['alarm_control_panel']


class TotalConnectSystem:
    """TotalConnect System class."""

    def __init__(self, username, password):
        """Initialize the TotalConnect system."""
        from total_connect_client import TotalConnectClient

        _LOGGER.debug("Setting up TotalConnectSystem...")
        self._username = username
        self._password = password
        self._client = TotalConnectClient.TotalConnectClient(username,
                                                             password)

    @property
    def client(self):
        """Return the client."""
        return self._client


def setup(hass, config):
    """Set up TotalConnect component."""
    conf = config.get(DOMAIN)
    if conf is not None:

        username = conf.get(CONF_USERNAME)
        password = conf.get(CONF_PASSWORD)

        hass.data[DOMAIN] = TotalConnectSystem(username, password)

        for platform in TOTALCONNECT_PLATFORMS:
            discovery.load_platform(hass, platform, DOMAIN, {}, config)

        return True

    _LOGGER.critical("TotalConnect configuration is missing.")
    return False
