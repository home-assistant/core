"""Diagnostics support for Belkin WeMo."""

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .models import DATA_WEMO


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    wemo_data = hass.data[DATA_WEMO]
    return {
        "discovery_enabled": wemo_data.discovery_enabled,
        "static_config_count": len(wemo_data.static_config),
        "devices": [
            {
                "model_name": coordinator.wemo.model_name,
                "model": coordinator.wemo.model,
                "firmware_version": coordinator.wemo.firmware_version,
                "supports_long_press": coordinator.supports_long_press,
                "subscribed": wemo_data.registry.is_subscribed(coordinator.wemo),
                "last_update_success": coordinator.last_update_success,
                "options": asdict(coordinator.options) if coordinator.options else None,
            }
            for coordinator in wemo_data.config_entry_data.device_coordinators.values()
        ],
    }
