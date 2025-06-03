"""Provide MQTT add-on management.

Currently only supports the official mosquitto add-on.
"""

from __future__ import annotations

from homeassistant.components.hassio import AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, LOGGER

ADDON_SLUG = "core_mosquitto"
DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass, LOGGER, "Mosquitto Mqtt Broker", ADDON_SLUG)
