"""Volvo diagnostics."""

from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_VIN
from .coordinator import VolvoConfigEntry

_TO_REDACT_ENTRY = [
    CONF_ACCESS_TOKEN,
    CONF_API_KEY,
    CONF_VIN,
    "id_token",
    "refresh_token",
]

_TO_REDACT_DATA = [
    "coordinates",
    "heading",
    "vin",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VolvoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    context = entry.runtime_data.interval_coordinators[0].context

    entity_registry = er.async_get(hass)
    entities: dict[str, str | None] = {}

    for reg_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        state = hass.states.get(reg_entry.entity_id)
        entities[reg_entry.entity_id] = state.state if state else None

    return {
        "entry_data": async_redact_data(entry.data, _TO_REDACT_ENTRY),
        "vechicle": async_redact_data(_to_dict(context.vehicle), _TO_REDACT_DATA),
        "entities": entities,
        **{
            coordinator.name: async_redact_data(
                _to_dict(coordinator.data), _TO_REDACT_DATA
            )
            for coordinator in entry.runtime_data.interval_coordinators
        },
    }


def _to_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        data = {}
        for k, v in obj.items():
            data[k] = _to_dict(v)
        return data

    if hasattr(obj, "__iter__") and not isinstance(obj, str):
        return [_to_dict(v) for v in obj]

    if hasattr(obj, "__dict__"):
        return {
            key: _to_dict(value)
            for key, value in obj.__dict__.items()
            if not callable(value) and not key.startswith("_")
        }

    return obj
