"""Provide add-on management."""
from __future__ import annotations

from homeassistant.components.hassio import AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import ADDON_SLUG, DOMAIN, LOGGER

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass, LOGGER, "Z-Wave JS", ADDON_SLUG)
