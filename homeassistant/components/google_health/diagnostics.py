"""Diagnostics support for Google Health."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from . import GoogleHealthConfigEntry

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    "refresh_token",
    "client_id",
    "client_secret",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GoogleHealthConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data

    activity_diagnostics = None
    if (activity_coordinator := data.activity_coordinator) is not None:
        activity_data = activity_coordinator.data
        activity_diagnostics = {
            "last_update_success": activity_coordinator.last_update_success,
            "steps": activity_data.steps is not None,
            "distance": activity_data.distance is not None,
            "active_energy_burned": activity_data.active_energy_burned is not None,
            "total_calories": activity_data.total_calories is not None,
            "floors": activity_data.floors is not None,
        }

    body_diagnostics = None
    if (body_coordinator := data.body_coordinator) is not None:
        body_data = body_coordinator.data
        body_diagnostics = {
            "last_update_success": body_coordinator.last_update_success,
            "weight": body_data.weight is not None,
            "resting_heart_rate": body_data.resting_heart_rate is not None,
            "body_fat": body_data.body_fat is not None,
        }

    sleep_diagnostics = None
    if (sleep_coordinator := data.sleep_coordinator) is not None:
        sleep_data = sleep_coordinator.data
        sleep_diagnostics = {
            "last_update_success": sleep_coordinator.last_update_success,
            "sleep": sleep_data.sleep is not None,
        }

    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "activity_coordinator": activity_diagnostics,
        "body_coordinator": body_diagnostics,
        "sleep_coordinator": sleep_diagnostics,
    }
