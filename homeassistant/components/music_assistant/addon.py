"""Provide Music Assistant add-on management.

Currently only supports the official Music Assistant add-on.
"""

from homeassistant.components.hassio import AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DEFAULT_NAME, DOMAIN, LOGGER

ADDON_SLUG = "d5369777_music_assistant"
DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass, LOGGER, DEFAULT_NAME, ADDON_SLUG)
