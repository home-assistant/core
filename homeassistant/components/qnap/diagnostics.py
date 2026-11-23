"""Diagnostics support for the qnap integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import QnapConfigEntry

TO_REDACT = {
    CONF_PASSWORD,
    CONF_USERNAME,
    "mac",
    "serial",
    "serial_number",
    "sharename",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: QnapConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "last_update_success": coordinator.last_update_success,
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }
