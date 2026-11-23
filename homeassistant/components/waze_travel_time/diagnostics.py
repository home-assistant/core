"""Diagnostics support for Waze Travel Time."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BASE_COORDINATES,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_ORIGIN,
)
from .coordinator import WazeTravelTimeConfigEntry

# The name and the street filters often point to home or work.
TO_REDACT = {
    CONF_BASE_COORDINATES,
    CONF_DESTINATION,
    CONF_EXCL_FILTER,
    CONF_INCL_FILTER,
    CONF_NAME,
    CONF_ORIGIN,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WazeTravelTimeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "data": async_redact_data(entry.data, TO_REDACT),
        "options": async_redact_data(entry.options, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "coordinator_data": async_redact_data(asdict(coordinator.data), TO_REDACT),
    }
