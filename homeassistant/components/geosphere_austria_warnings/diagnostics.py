"""Diagnostics support for the GeoSphere Austria Warnings integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .coordinator import GeoSphereConfigEntry

# The coordinates are the user's chosen location, often their home.
TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GeoSphereConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diagnostics: dict[str, Any] = {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
    }

    # An entry that is not loaded has no coordinator, so report the entry alone.
    if entry.state is ConfigEntryState.LOADED:
        coordinator = entry.runtime_data
        diagnostics["last_update_success"] = coordinator.last_update_success
        if (data := coordinator.data) is not None:
            diagnostics["location_warnings"] = asdict(data.location_warnings)

    return diagnostics
