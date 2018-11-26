"""
Support for ecoal/esterownik.pl coal/wood boiler controller.

Allows read various readings available in controller
and set very basic switches.
"""
import logging

# import voluptuous as vol
# import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PASSWORD


_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecoal_boiler"
DATA_ECOAL_BOILER = 'data_' + DOMAIN


CONF_USERNAME = "username"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"

# CONFIG_SCHEMA = vol.Schema({
#    DOMAIN: vol.Schema({
#        vol.Required(CONF_HOST): cv.string,
#        vol.Optional(CONF_USERNAME,
#                        default=DEFAULT_USERNAME): cv.string,
#        vol.Optional(CONF_PASSWORD,
#                        default=DEFAULT_PASSWORD): cv.string,
#    })
# })
# Fails with:
# Invalid config for [ecoal_boiler]:
#   [homeassistant] is an invalid option for [ecoal_boiler].

# In fact it is variable, set during setup
## ECOAL_CONTR = None


async def async_setup(hass, config):
    """Set up global ECoalControler instance same for sensors and switches."""
    _LOGGER.debug("async_setup(): config: %r", config)
    from .http_iface import ECoalControler

    conf = config.get(DOMAIN)
    _LOGGER.debug(
        "async_setup(): conf: %r  conf.keys(): %r", conf, conf.keys()
    )

    host = conf.get(CONF_HOST)
    username = conf.get(CONF_USERNAME)
    passwd = conf.get(CONF_PASSWORD)
    _LOGGER.debug(
        "async_setup(): host: %r username: %r passwd: %r", host, username, passwd
    )
    ecoal_contr = ECoalControler(host, username, passwd)
    hass.data[DATA_ECOAL_BOILER] = ecoal_contr
    return True
