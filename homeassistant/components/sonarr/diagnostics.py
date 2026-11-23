"""Diagnostics support for Sonarr."""

from dataclasses import fields
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import SonarrConfigEntry, SonarrDataUpdateCoordinator

TO_REDACT = {CONF_API_KEY}


def _model_to_dict(model: Any) -> dict[str, Any]:
    # aiopyarr only sets the fields that the Sonarr response contains.
    return {
        field.name: getattr(model, field.name)
        for field in fields(model)
        if hasattr(model, field.name)
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SonarrConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    coordinators: dict[str, SonarrDataUpdateCoordinator[Any]] = {
        "commands": data.commands,
        "diskspace": data.diskspace,
        "queue": data.queue,
        "series": data.series,
        "status": data.status,
        "upcoming": data.upcoming,
        "wanted": data.wanted,
    }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "entry_options": dict(entry.options),
        "last_update_success": {
            name: coordinator.last_update_success
            for name, coordinator in coordinators.items()
        },
        "disks": [_model_to_dict(disk) for disk in data.diskspace.data],
    }
