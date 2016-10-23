"""Allows the LiteJet lighting system to be controlled by Home Assistant.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/litejet/
"""
import logging
import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv

DOMAIN = 'litejet'

REQUIREMENTS = ['pylitejet>=0.1']

CONF_EXCLUDE_NAMES = 'exclude_names'
CONF_INCLUDE_SWITCHES = 'include_switches'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_EXCLUDE_NAMES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_INCLUDE_SWITCHES, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

CONNECTION = None
CONFIG = None


def setup(hass, config):
    """Initializes the LiteJet component."""

    from pylitejet import LiteJet

    global CONNECTION, CONFIG

    url = config[DOMAIN].get(CONF_URL)

    CONNECTION = LiteJet(url)
    CONFIG = config[DOMAIN]

    discovery.load_platform(hass, 'light', DOMAIN, {}, config)
    if config[DOMAIN].get(CONF_INCLUDE_SWITCHES):
        discovery.load_platform(hass, 'switch', DOMAIN, {}, config)
    discovery.load_platform(hass, 'scene', DOMAIN, {}, config)

    return True


def is_ignored(name):
    """Determines if a load, switch, or scene should be ignored
    based on its name. This is called by each platform during setup.
    """
    for prefix in CONFIG.get(CONF_EXCLUDE_NAMES, []):
        if name.startswith(prefix):
            return True
    return False
