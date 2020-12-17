"""The flux_led component."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Flux LED/MagicLight component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Flux LED/MagicLight from a config entry."""
    conf = entry.data

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_TYPE: conf[CONF_TYPE],
        CONF_HOST: conf[CONF_HOST],
        CONF_NAME: conf[CONF_NAME],
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True
