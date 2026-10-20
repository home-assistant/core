"""Diagnostics support for Sofar."""

from dataclasses import asdict
from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import SofarConfigEntry

TO_REDACT = {"serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SofarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    device = runtime_data.readings.device
    raw = masks = read_error = None
    try:
        raw = await device.async_read_raw(redact_serial=True)
        masks = await device.async_read_masks()
    except ModbusError as err:
        read_error = type(err).__name__

    return async_redact_data(
        {
            "model": device.model,
            "inverter_type": device.inverter_type,
            "serial_number": device.serial_number,
            "readings_components": device.readings_components,
            "settings_components": device.settings_components,
            "active_faults": sorted(fault.key for fault in device.state.active_faults),
            "address_masks": masks,
            "link": {
                "tuning": asdict(device.link_tuning),
                "stats": asdict(device.link_stats),
            },
            "read_error": read_error,
            "raw": raw,
        },
        TO_REDACT,
    )
