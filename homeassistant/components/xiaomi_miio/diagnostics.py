"""Diagnostics support for Xiaomi Miio."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_TOKEN, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .const import CONF_CLOUD_PASSWORD, CONF_CLOUD_USERNAME, DOMAIN, KEY_COORDINATOR

TO_REDACT = {
    CONF_CLOUD_PASSWORD,
    CONF_CLOUD_USERNAME,
    CONF_MAC,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics_data: dict[str, Any] = {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT)
    }

    # not every device uses DataUpdateCoordinator
    if coordinator := hass.data[DOMAIN][config_entry.entry_id].get(KEY_COORDINATOR):
        if isinstance(coordinator.data, dict):
            diagnostics_data["coordinator_data"] = coordinator.data
        else:
            diagnostics_data["coordinator_data"] = repr(coordinator.data)

    return diagnostics_data
