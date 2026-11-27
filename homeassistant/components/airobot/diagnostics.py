"""Diagnostics support for Airobot."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import AirobotConfigEntry

TO_REDACT_CONFIG = [CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirobotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT_CONFIG),
        "device_capabilities": {
            "has_floor_sensor": coordinator.data.status.has_floor_sensor,
            "has_co2_sensor": coordinator.data.status.has_co2_sensor,
            "hw_version": coordinator.data.status.hw_version,
            "fw_version": coordinator.data.status.fw_version,
        },
        "status": asdict(coordinator.data.status),
        "settings": asdict(coordinator.data.settings),
    }
