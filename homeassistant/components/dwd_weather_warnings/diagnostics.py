"""Diagnostics support for the dwd_weather_warnings integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_REGION_DEVICE_TRACKER, CONF_REGION_IDENTIFIER
from .coordinator import DwdWeatherWarningsConfigEntry

# The tracker points to the user's position, a warncell ID or name is public.
TO_REDACT = {CONF_REGION_DEVICE_TRACKER}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DwdWeatherWarningsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    api = coordinator.api

    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "region_source": (
            CONF_REGION_IDENTIFIER
            if CONF_REGION_IDENTIFIER in entry.data
            else CONF_REGION_DEVICE_TRACKER
        ),
        "last_update_success": coordinator.last_update_success,
        "api": {
            "data_valid": api.data_valid,
            "warncell_id": api.warncell_id,
            "warncell_name": api.warncell_name,
            "last_update": api.last_update,
            "current_warning_level": api.current_warning_level,
            "current_warnings": api.current_warnings,
            "expected_warning_level": api.expected_warning_level,
            "expected_warnings": api.expected_warnings,
        },
    }
