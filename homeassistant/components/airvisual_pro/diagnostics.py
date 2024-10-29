"""Support for AirVisual Pro diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import AirVisualProConfigEntry

CONF_MAC_ADDRESS = "mac_address"
CONF_SERIAL_NUMBER = "serial_number"

TO_REDACT = {
    CONF_MAC_ADDRESS,
    CONF_PASSWORD,
    CONF_SERIAL_NUMBER,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirVisualProConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": entry.runtime_data.coordinator.data,
        },
        TO_REDACT,
    )
