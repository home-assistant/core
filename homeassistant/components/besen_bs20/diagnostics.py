"""Diagnostics for Besen BS20."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant

from . import BesenBS20ConfigEntry

TO_REDACT = {CONF_PIN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    coordinator = entry.runtime_data.coordinator
    state = coordinator.data or coordinator.client.state
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "state": {
            "available": state.available,
            "authenticated": state.authenticated,
            "last_error": state.last_error,
            "info": asdict(state.info),
            "config": asdict(state.config),
            "charge": asdict(state.charge),
            "last_command": asdict(state.last_command)
            if state.last_command is not None
            else None,
        },
    }
