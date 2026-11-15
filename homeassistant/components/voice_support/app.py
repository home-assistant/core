"""The Voice app, as a Home Assistant app managed by the Supervisor."""

import logging

from homeassistant.components.hassio import AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN

APP_NAME = "Voice"
APP_SLUG = "core_voice"

DATA_APP_MANAGER = f"{DOMAIN}_app_manager"

_LOGGER = logging.getLogger(__name__)


@singleton(DATA_APP_MANAGER)
@callback
def get_app_manager(hass: HomeAssistant) -> AddonManager:
    """Get the app manager."""
    return AddonManager(hass, _LOGGER, APP_NAME, APP_SLUG)
