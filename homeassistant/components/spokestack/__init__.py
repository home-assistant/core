"""The Spokestack TTS component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["tts"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Spokestack from a config entry."""
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data["voice"]

    hass.data[DOMAIN].update(entry.data)
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True
