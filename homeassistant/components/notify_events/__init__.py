"""The notify_events component."""
import voluptuous as vol

from homeassistant.const import CONF_TOKEN
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_TOKEN): cv.string})}, extra=vol.ALLOW_EXTRA
)


def setup(hass, config):
    """Set up the notify_events component."""

    hass.data[DOMAIN] = config[DOMAIN]
    discovery.load_platform(hass, "notify", DOMAIN, {}, config)
    return True
