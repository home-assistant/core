"""Volvo diagnostics."""

from dataclasses import asdict
from typing import Any

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.core import HomeAssistant
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
    data: dict[str, dict] = {}

    for coordinator in entry.runtime_data.interval_coordinators:
        data[coordinator.name] = {
            key: async_redact_data(asdict(value), _TO_REDACT_DATA) if value else None
            for key, value in coordinator.data.items()
        }

    return {
        "entry_data": async_redact_data(entry.data, _TO_REDACT_ENTRY),
        "vehicle": async_redact_data(asdict(context.vehicle), _TO_REDACT_DATA),
        **data,
    }
