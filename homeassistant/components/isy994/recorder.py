"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude frequently changing attributes from the database."""
    return {
        "actions_enabled",
        "actions_last_update",
        "ran_else",
        "ran_then",
        "run_at_startup",
        "running",
        "status_enabled",
        "status_last_update",
    }
