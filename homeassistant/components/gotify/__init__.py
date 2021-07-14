"""The gotify component."""
import voluptuous as vol

from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_TOKEN): cv.string, vol.Required(CONF_URL): cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the gotify component."""
    hass.data[DOMAIN] = config[DOMAIN]
    discovery.load_platform(hass, "notify", DOMAIN, {}, config)
    return True
