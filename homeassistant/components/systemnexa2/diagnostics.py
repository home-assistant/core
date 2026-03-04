"""Diagnostics support for System Nexa 2."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import SystemNexa2ConfigEntry

TO_REDACT = {
    CONF_HOST,
    CONF_DEVICE_ID,
    "unique_id",
    "wifi_ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SystemNexa2ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "device_info": async_redact_data(asdict(coordinator.data.info_data), TO_REDACT),
        "coordinator_available": coordinator.last_update_success,
        "state": coordinator.data.state,
        "settings": {
            name: {
                "name": setting.name,
                "enabled": setting.is_enabled(),
            }
            for name, setting in coordinator.data.on_off_settings.items()
        },
    }
