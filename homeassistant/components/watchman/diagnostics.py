"""Diagnostics support for Kingspan Watchman SENSiT."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .coordinator import SENSiTConfigEntry

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "serial_number",
}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: SENSiTConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "config_entry_data": async_redact_data(entry.data, TO_REDACT),
        "config_entry_options": async_redact_data(entry.options, TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "tank_count": len(coordinator.data),
        "tanks": [
            async_redact_data(asdict(tank), TO_REDACT) for tank in coordinator.data
        ],
    }
