"""Diagnostics support for InComfort integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback

from .coordinator import InComfortConfigEntry

REDACT_CONFIG = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: InComfortConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return _async_get_diagnostics(hass, entry)


@callback
def _async_get_diagnostics(
    hass: HomeAssistant,
    entry: InComfortConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    redacted_config = async_redact_data(entry.data | entry.options, REDACT_CONFIG)
    coordinator = entry.runtime_data

    nr_heaters = len(coordinator.incomfort_data.heaters)
    status: dict[str, Any] = {
        f"heater_{n}": coordinator.incomfort_data.heaters[n].status
        for n in range(nr_heaters)
    }
    for n in range(nr_heaters):
        status[f"heater_{n}"]["rooms"] = {
            m: dict(coordinator.incomfort_data.heaters[n].rooms[m].status)
            for m in range(len(coordinator.incomfort_data.heaters[n].rooms))
        }
    return {
        "config": redacted_config,
        "gateway": status,
    }
