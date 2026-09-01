"""Diagnostics support for Sofar."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import SofarConfigEntry

TO_REDACT = {"serial_number"}

_SERIAL_NUMBER_REGISTERS = range(0x0445, 0x044C)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SofarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = entry.runtime_data.readings.device
    raw = await device.async_read_raw()
    if (holding := raw.get("holding")) is not None:
        for address in _SERIAL_NUMBER_REGISTERS:
            holding.pop(address, None)

    return async_redact_data(
        {
            "model": device.model,
            "inverter_type": device.inverter_type,
            "serial_number": device.serial_number,
            "readings_components": device.readings_components,
            "settings_components": device.settings_components,
            "raw": raw,
        },
        TO_REDACT,
    )
