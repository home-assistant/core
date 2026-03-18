"""Diagnostics support for the SunSynk integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import (
    async_redact_data,  # pyright: ignore[reportUnknownVariableType]
)
from homeassistant.core import HomeAssistant

from . import SunSynkConfigEntry
from .const import CONF_EMAIL, CONF_PASSWORD

REDACT_CONFIG = {CONF_EMAIL, CONF_PASSWORD}
REDACT_DATA = {"token", "access_token", "refresh_token", "email", "password"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SunSynkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    coordinator_data: dict[str, Any] = coordinator.data or {}

    # Summarise plants and inverters without leaking tokens
    plants_summary: dict[str, Any] = {}
    for plant_id, plant_data in coordinator_data.get("plants", {}).items():
        inverters_summary: dict[str, Any] = {}
        for sn, inv_data in plant_data.get("inverters", {}).items():
            inverters_summary[sn] = {
                "has_battery": inv_data.get("battery") is not None,
                "has_grid": inv_data.get("grid") is not None,
                "has_load": inv_data.get("load") is not None,
                "has_input": inv_data.get("input") is not None,
                "has_settings": inv_data.get("settings") is not None,
            }
        plants_summary[str(plant_id)] = {
            "inverter_count": len(plant_data.get("inverters", {})),
            "inverters": inverters_summary,
        }

    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception)
            if coordinator.last_exception
            else None,
            "update_interval": str(coordinator.update_interval),
        },
        "data_summary": {
            "plant_count": len(coordinator_data.get("plants", {})),
            "gateway_count": len(coordinator_data.get("gateways", [])),
            "plants": plants_summary,
        },
    }
