"""The Spokestack TTS component."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS = ["tts"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Hello World component."""
    # Ensure our name space for storing objects is a known type. A dict is
    # common/preferred as it allows a separate instance of your class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Spokestack from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = entry.data["voice"]

    hass.data[DOMAIN].update(entry.data)
    for component in PLATFORMS:
        hass.async_create_task(
            hass.helpers.discovery.async_load_platform(
                component, DOMAIN, {}, hass_config=hass.data
            )
        )

    return True
