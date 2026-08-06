"""Diagnostics support for Tewke."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from .data import TewkeConfigEntry

TO_REDACT = {
    CONF_HOST,
    "hardwareId",
    "hardware_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TewkeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data.coordinator.data

    diagnostics_data: dict[str, Any] = {
        "scenes": {k: v.model_dump() for k, v in data["scenes"].items()}
        if data.get("scenes")
        else {},
        "targets": {k: v.model_dump() for k, v in data["targets"].items()}
        if data.get("targets")
        else {},
        "sensors": s.model_dump() if (s := data.get("sensors")) else None,
        "radar": r.model_dump() if (r := data.get("radar")) else None,
        "energy": e.model_dump() if (e := data.get("energy")) else None,
        "energy_override": eo.model_dump()
        if (eo := data.get("energy_override"))
        else None,
        "config": async_redact_data(c.model_dump(), TO_REDACT)
        if (c := data.get("config"))
        else None,
    }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": diagnostics_data,
    }
