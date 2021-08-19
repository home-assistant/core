"""The Spokestack TTS component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Spokestack from a config entry."""
    # Add DOMAIN key to home-assistant main config.
    hass.data.setdefault(DOMAIN, {})
    # Set the config entry under the DOMAIN key.
    hass.data[DOMAIN] = entry.data
    # Load tts platform since we can't pass the entry to async_setup_entry
    # since homeassistant.components.tts does not have an attribute async_setup_entry.
    for component in PLATFORMS:
        hass.async_create_task(
            async_load_platform(
                hass, component, DOMAIN, hass.data[DOMAIN], hass_config=hass.data
            )
        )
    return True
