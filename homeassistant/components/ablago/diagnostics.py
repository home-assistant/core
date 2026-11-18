"""Diagnostics for the Ablago integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from .coordinator import AblagoConfigEntry

# The address can point into the home network or name the household; the key opens the counters.
TO_REDACT = {CONF_API_KEY, CONF_URL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AblagoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    health = data.health.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "counters": asdict(data.counters.data),
        "health": asdict(health) if health is not None else None,
    }
