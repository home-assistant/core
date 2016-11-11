"""
Support for Neato botvac connected vacuum cleaners.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/neato/
"""
import logging
from datetime import timedelta
from urllib.error import HTTPError

import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/jabesq/pybotvac/archive/v0.0.1.zip'
                '#pybotvac==0.0.1']

DOMAIN = 'neato'
NEATO_ROBOTS = 'neato_robots'
NEATO_LOGIN = 'neato_login'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Setup the Verisure component."""
    from pybotvac import Account

    hass.data[NEATO_LOGIN] = NeatoHub(hass, config[DOMAIN], Account)
    hub = hass.data[NEATO_LOGIN]
    if not hub.login():
        _LOGGER.debug('Failed to login to Neato API')
        return False
    hub.update_robots()
    for component in ('sensor', 'switch'):
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class NeatoHub(object):
    """A My Neato hub wrapper class."""

    def __init__(self, hass, domain_config, neato):
        """Initialize the Neato hub."""
        self.config = domain_config
        self._neato = neato
        self._hass = hass

        self.my_neato = neato(
            domain_config[CONF_USERNAME],
            domain_config[CONF_PASSWORD])
        self._hass.data[NEATO_ROBOTS] = self.my_neato.robots

    def login(self):
        """Login to My Neato."""
        try:
            _LOGGER.debug('Trying to connect to Neato API')
            self.my_neato = self._neato(self.config[CONF_USERNAME],
                                        self.config[CONF_PASSWORD])
            return True
        except HTTPError:
            _LOGGER.error("Unable to connect to Neato API")
            return False

    @Throttle(timedelta(seconds=1))
    def update_robots(self):
        """Update the robot states."""
        _LOGGER.debug('Running HUB.update_robots %s',
                      self._hass.data[NEATO_ROBOTS])
        self._hass.data[NEATO_ROBOTS] = self.my_neato.robots
