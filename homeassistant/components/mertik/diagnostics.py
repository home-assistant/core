"""Diagnostics support for Mertik Maxitrol Fireplace."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import MertikConfigEntry

TO_REDACT = [CONF_HOST]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MertikConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "options": entry.options,
        "coordinator": {
            "is_on": coordinator.is_on,
            "is_aux_on": coordinator.is_aux_on,
            "ambient_temperature": coordinator.ambient_temperature,
            "heating_mode": coordinator.heating_mode,
            "flame_height": coordinator.get_flame_height(),
            "is_light_on": coordinator.is_light_on,
            "in_standby": coordinator._in_standby,
            "pending_mode": coordinator._pending_mode,
        },
    }
