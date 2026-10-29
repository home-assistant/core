"""Diagnostics for aerosmart."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import AerosmartConfigEntry

TO_REDACT = {CONF_DEVICE, CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AerosmartConfigEntry
) -> dict[str, Any]:
    """Return a redacted snapshot of the connection and update state."""
    del hass
    runtime = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "readings": {
            "last_update_success": runtime.readings.last_update_success,
            "updated_components": sorted(runtime.readings.data.updated),
            "failed_components": sorted(runtime.readings.data.failed),
        },
        "settings": {
            "last_update_success": runtime.settings.last_update_success,
            "updated_components": sorted(runtime.settings.data.updated),
            "failed_components": sorted(runtime.settings.data.failed),
        },
    }
