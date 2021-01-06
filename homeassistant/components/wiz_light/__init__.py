"""WiZ Light integration."""
import logging

from pywizlight import wizlight

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Old way of setting up the wiz_light component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the wiz_light integration from a config entry."""
    ip_address = entry.data.get(CONF_HOST)
    _LOGGER.debug("Get bulb with IP: %s", ip_address)
    bulb = wizlight(ip_address)
    hass.data[DOMAIN][entry.unique_id] = bulb

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # unload wiz_light bulb
    hass.data[DOMAIN][entry.unique_id] = None
    # Remove config entry
    await hass.config_entries.async_forward_entry_unload(entry, "light")

    return True
