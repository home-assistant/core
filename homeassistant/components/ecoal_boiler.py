"""
Component to control ecoal/esterownik.pl coal/wood boiler controller.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ecoal_boiler/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD,  CONF_USERNAME

REQUIREMENTS = ['ecoaliface==0.4.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecoal_boiler"
DATA_ECOAL_BOILER = 'data_' + DOMAIN

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME,
                     default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD,
                     default=DEFAULT_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up global ECoalController instance same for sensors and switches."""
    from ecoaliface.simple import ECoalController

    conf = config[DOMAIN]
    host = conf[CONF_HOST]
    username = conf[CONF_USERNAME]
    passwd = conf[CONF_PASSWORD]
    ecoal_contr = ECoalController(host, username, passwd)
    # Creating ECoalController instance makes HTTP request to controller.
    if ecoal_contr.version is None:
        # Wrong credentials nor network config
        return False
    hass.data[DATA_ECOAL_BOILER] = ecoal_contr
    _LOGGER.debug("Detected controller version: %r @%s", ecoal_contr.version,  host, )
    return True
