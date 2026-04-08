"""Provide add-on management."""

from __future__ import annotations

from typing import Any

from homeassistant.components.hassio import AddonError, AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.redact import async_redact_data
from homeassistant.helpers.singleton import singleton

from .const import (
    ADDON_SLUG,
    CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_LR_S2_AUTHENTICATED_KEY,
    CONF_ADDON_NETWORK_KEY,
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
    DOMAIN,
    LOGGER,
)

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"
REDACT_ADDON_OPTION_KEYS = {
    CONF_ADDON_S0_LEGACY_KEY,
    CONF_ADDON_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_S2_AUTHENTICATED_KEY,
    CONF_ADDON_S2_UNAUTHENTICATED_KEY,
    CONF_ADDON_LR_S2_ACCESS_CONTROL_KEY,
    CONF_ADDON_LR_S2_AUTHENTICATED_KEY,
    CONF_ADDON_NETWORK_KEY,
}


def _redact_sensitive_option_values(message: str, config: dict[str, Any]) -> str:
    """Redact sensitive add-on option values in an error string."""
    redacted_config = async_redact_data(config, REDACT_ADDON_OPTION_KEYS)

    for key in REDACT_ADDON_OPTION_KEYS:
        option_value = config.get(key)
        if not isinstance(option_value, str) or not option_value:
            continue
        redacted_value = redacted_config.get(key)
        if not isinstance(redacted_value, str):
            continue
        message = message.replace(option_value, redacted_value)

    return message


class ZwaveAddonManager(AddonManager):
    """Addon manager for Z-Wave JS with redacted option errors."""

    async def async_set_addon_options(self, config: dict[str, Any]) -> None:
        """Set add-on options."""
        try:
            await super().async_set_addon_options(config)
        except AddonError as err:
            raise AddonError(
                _redact_sensitive_option_values(str(err), config)
            ) from None


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return ZwaveAddonManager(hass, LOGGER, "Z-Wave JS", ADDON_SLUG)
