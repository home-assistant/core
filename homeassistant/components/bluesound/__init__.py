"""The bluesound component."""
import logging

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_NAME
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bluesound from a config entry."""
    _LOGGER.debug("Bluesound async_setup_entry with %r", entry)
