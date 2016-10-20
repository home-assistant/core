"""Allows the LiteJet lighting system to be controlled by Home Assistant."""
import logging
import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv

DOMAIN = 'litejet'

REQUIREMENTS = ['pylitejet>=0.1']

CONF_IGNORE = 'ignore'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_IGNORE) : vol.All(cv.ensure_list, [cv.string])
    })
}, extra=vol.ALLOW_EXTRA)

CONNECTION = None
CONFIG = None


def setup(hass, config):
    """Initializes the LiteJet component."""

    from pylitejet import LiteJet

    global CONNECTION, CONFIG

    url = config[DOMAIN].get(CONF_URL)

    _LOGGER.info('Opening %s"', url)
    CONNECTION = LiteJet(url)
    CONFIG = config[DOMAIN]

    discovery.load_platform(hass, 'light', DOMAIN, {}, config)
    discovery.load_platform(hass, 'switch', DOMAIN, {}, config)
    discovery.load_platform(hass, 'scene', DOMAIN, {}, config)

    return True

def is_ignored(name):
    """Determines if a load, switch, or scene should be ignored based on its name."""
    for prefix in CONFIG.get(CONF_IGNORE, []):
        if name.startswith(prefix):
            return True
    return False
