"""Diagnostics support for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import LeilSaunaConfigEntry

REDACT_CONFIG = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LeilSaunaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Build diagnostics data
    diagnostics_data: dict[str, Any] = {
        "config": async_redact_data(entry.data, REDACT_CONFIG),
        "client_info": {"connected": coordinator.client.is_connected},
        "coordinator_info": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "last_exception": str(coordinator.last_exception)
            if coordinator.last_exception
            else None,
        },
    }

    # Add coordinator data if available
    if coordinator.data:
        data_dict = asdict(coordinator.data)
        diagnostics_data["coordinator_data"] = data_dict

        # Add alarm summary
        alarm_fields = [
            key
            for key, value in data_dict.items()
            if key.startswith("alarm_") and value is True
        ]
        diagnostics_data["active_alarms"] = alarm_fields

    return diagnostics_data
