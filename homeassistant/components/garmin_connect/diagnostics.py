"""Diagnostics support for Garmin Connect."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import GarminConnectConfigEntry

TO_REDACT = {
    "oauth1_token",
    "oauth2_token",
    "displayName",
    "fullName",
    "userName",
    "email",
    "profileImageUrlMedium",
    "profileImageUrlSmall",
    "profileImageUrlLarge",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GarminConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = entry.runtime_data
    # Use core coordinator for main data
    core_coordinator = coordinators.core
    data = core_coordinator.data or {}

    # Count sensors by category
    sensor_counts: dict[str, int] = {}
    for key in data:
        if key.startswith("total"):
            category = "totals"
        elif key.startswith("yesterday"):
            category = "yesterday"
        elif key.startswith("weekly"):
            category = "weekly"
        elif "stress" in key.lower():
            category = "stress"
        elif "sleep" in key.lower():
            category = "sleep"
        elif "heart" in key.lower() or "hr" in key.lower():
            category = "heart"
        elif "battery" in key.lower():
            category = "body_battery"
        elif "activity" in key.lower():
            category = "activity"
        else:
            category = "other"
        sensor_counts[category] = sensor_counts.get(category, 0) + 1

    # Get sample of data keys (not values for privacy)
    data_keys = list(data.keys())

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "data_keys_count": len(data_keys),
        "sensor_categories": sensor_counts,
        "data_keys_sample": data_keys[:50] if len(data_keys) > 50 else data_keys,
        "last_update_success": core_coordinator.last_update_success,
        "update_interval_seconds": (
            core_coordinator.update_interval.total_seconds()
            if core_coordinator.update_interval
            else None
        ),
    }
