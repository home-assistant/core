"""Provide add-on management."""

from __future__ import annotations

from typing import Any

from homeassistant.components.hassio import AddonError, AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import ADDON_SLUG, DOMAIN, LOGGER

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"
ERROR_SET_ADDON_OPTIONS = "Failed to set the Z-Wave JS app options"


class ZwaveAddonManager(AddonManager):
    """Addon manager for Z-Wave JS with redacted option errors."""

    async def async_set_addon_options(self, config: dict[str, Any]) -> None:
        """Set add-on options."""
        try:
            await super().async_set_addon_options(config)
        except AddonError:
            raise AddonError(ERROR_SET_ADDON_OPTIONS) from None


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return ZwaveAddonManager(hass, LOGGER, "Z-Wave JS", ADDON_SLUG)
