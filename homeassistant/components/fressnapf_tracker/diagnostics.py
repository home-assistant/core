"""Diagnostics support for Fressnapf Tracker."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import FressnapfTrackerConfigEntry

TO_REDACT = {
    "additional_parameters",
    "inside_geofence",
    "last_position",
    "lat",
    "lng",
    "serialnumber",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FressnapfTrackerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "trackers": [
                coordinator.data.model_dump(mode="json")
                for coordinator in entry.runtime_data
            ],
        },
        TO_REDACT,
    )
