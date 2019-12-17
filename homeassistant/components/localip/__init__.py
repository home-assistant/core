"""Get the local IP (eth0 equivalent) of the Home Assistant instance."""
import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "localip"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Optional(CONF_NAME, default=DOMAIN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the component."""
    hass.data[DOMAIN] = {CONF_NAME: config[DOMAIN][CONF_NAME]}
    hass.async_create_task(async_load_platform(hass, "sensor", DOMAIN, {}, config))
    return True
