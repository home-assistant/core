"""Diagnostics support for La Marzocco."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .const import CONF_USE_BLUETOOTH
from .coordinator import LaMarzoccoConfigEntry

TO_REDACT = {
    "serial_number",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.config_coordinator
    device = coordinator.device
    data = {
        "device": device.to_dict(),
        "bluetooth_available": (
            entry.options.get(CONF_USE_BLUETOOTH, True)
            and CONF_MAC in entry.data
            and CONF_TOKEN in entry.data
        ),
    }
    return async_redact_data(data, TO_REDACT)
