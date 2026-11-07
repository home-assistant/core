"""Provide add-on management."""

from typing import Any

from homeassistant.components.hassio import AddonError, AddonManager
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import ADDON_SLUG, CONF_ADDON_BLE_PROXY, DOMAIN, LOGGER

DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Get the add-on manager."""
    return AddonManager(hass, LOGGER, "Matter Server", ADDON_SLUG)


async def async_enable_ble_proxy(
    addon_manager: AddonManager, options: dict[str, Any]
) -> bool:
    """Turn on the app's BLE proxy option and report whether it was set.

    The proxy is optional, so a failure is logged rather than raised.
    """
    try:
        await addon_manager.async_set_addon_options(
            {**options, CONF_ADDON_BLE_PROXY: True}
        )
    except AddonError as err:
        LOGGER.warning("Failed to enable the Matter Server app BLE proxy: %s", err)
        return False
    return True
