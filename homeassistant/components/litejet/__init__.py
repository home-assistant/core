"""Support for the LiteJet lighting system."""
import logging

from pylitejet import LiteJet
import voluptuous as vol

from homeassistant.const import CONF_PORT
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE_NAMES = "exclude_names"
CONF_INCLUDE_SWITCHES = "include_switches"

DOMAIN = "litejet"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_PORT): cv.string,
                vol.Optional(CONF_EXCLUDE_NAMES): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional(CONF_INCLUDE_SWITCHES, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the LiteJet component."""

    url = config[DOMAIN].get(CONF_PORT)

    hass.data["litejet_system"] = LiteJet(url)
    hass.data["litejet_config"] = config[DOMAIN]

    discovery.load_platform(hass, "light", DOMAIN, {}, config)
    if config[DOMAIN].get(CONF_INCLUDE_SWITCHES):
        discovery.load_platform(hass, "switch", DOMAIN, {}, config)
    discovery.load_platform(hass, "scene", DOMAIN, {}, config)

    return True


def is_ignored(hass, name):
    """Determine if a load, switch, or scene should be ignored."""
    for prefix in hass.data["litejet_config"].get(CONF_EXCLUDE_NAMES, []):
        if name.startswith(prefix):
            return True
    return False
