"""Get the local IP address of the Home Assistant instance."""
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

DOMAIN = "localip"
PLATFORM = "sensor"

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Optional(CONF_NAME, default=DOMAIN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up localip from configuration.yaml."""
    hass.data[DOMAIN] = {}

    conf = config.get(DOMAIN)
    if conf:
        hass.data[DOMAIN][CONF_NAME] = config.get(DOMAIN)[CONF_NAME]
        hass.async_create_task(async_load_platform(hass, PLATFORM, DOMAIN, {}, config))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up localip from a config entry."""
    hass.data[DOMAIN] = {CONF_NAME: entry.data["name"]}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, PLATFORM)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    return await hass.config_entries.async_forward_entry_unload(entry, PLATFORM)
