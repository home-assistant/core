"""WiZ Light integration."""
import logging

from pywizlight import wizlight

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


PLATFORMS = ["light"]


async def async_setup(hass, config):
    """Old way of setting up the wiz_light component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the wiz_light integration from a config entry."""
    try:
        bulb = wizlight(entry.data.get(CONF_HOST))
        hass.data[DOMAIN] = bulb
    except (Exception) as ex:
        _LOGGER.error("Unable to connect to wiz_light: %s", str(ex))
        raise ConfigEntryNotReady from ex

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload a config entry."""
    # unload srp client
    hass.data[DOMAIN] = None
    # Remove config entry
    await hass.config_entries.async_forward_entry_unload(config_entry, "light")

    return True
