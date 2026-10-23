"""Diagnostics platform for the Gree Infrared integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import GreeInfraredConfigEntry

_STATE_FIELDS = (
    "turbo",
    "light",
    "health",
    "xfan",
    "sleep",
    "ifeel",
    "swing_v",
    "swing_h",
    "swing_h_position",
    "econo",
    "absence",
    "fahrenheit",
    "display_temp",
    "swing_v_position",
    "fresh_air",
    "timer_hours",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GreeInfraredConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    state = entry.runtime_data
    return {
        "entry_data": dict(entry.data),
        "ac_state": {field: getattr(state, field) for field in _STATE_FIELDS},
    }
