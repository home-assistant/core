"""Diagnostics support for Fast.com."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import FastdotcomConfigEntry

TO_REDACT = {"ip", "name", "url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: FastdotcomConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the config entry."""
    data = config_entry.runtime_data.data
    if data is None:
        return {"coordinator_data": None}
    coordinator_data = {
        **asdict(data),
        "unloaded_pings": list(data.unloaded_pings),
        "loaded_pings": list(data.loaded_pings),
        "targets": [asdict(target) for target in data.targets],
    }
    return {"coordinator_data": async_redact_data(coordinator_data, TO_REDACT)}
