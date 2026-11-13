"""Diagnostics for the Spin EV Charger integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL
from .coordinator import SpinEvConfigEntry

TO_REDACT = {CONF_ADDRESS, CONF_SERIAL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SpinEvConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    status = entry.runtime_data.data
    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "status": {
            **asdict(status),
            "state": status.state.name if status.state else None,
            "alarms": list(status.alarms),
        },
    }
