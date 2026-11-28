"""Provide Home Assistant app management."""

from homeassistant.components.hassio import AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import APP_NAME, APP_SLUG, DOMAIN, LOGGER

DATA_APP_MANAGER = f"{DOMAIN}_app_manager"


@singleton(DATA_APP_MANAGER)
@callback
def get_app_manager(hass: HomeAssistant) -> AddonManager:
    """Get the app manager."""
    return AddonManager(hass, LOGGER, APP_NAME, APP_SLUG)
