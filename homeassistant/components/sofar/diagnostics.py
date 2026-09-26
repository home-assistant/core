"""Diagnostics support for Sofar."""

from dataclasses import asdict
from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator

TO_REDACT = {"serial_number"}

_SERIAL_NUMBER_REGISTERS = range(0x0445, 0x044C)


def _last_error(coordinator: SofarDataUpdateCoordinator) -> str | None:
    """Return why a coordinator's last poll failed, if it did."""
    if coordinator.last_update_success or (err := coordinator.last_exception) is None:
        return None
    return type(err.__cause__ or err).__name__


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SofarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    device = runtime_data.readings.device
    raw = masks = read_error = None
    try:
        raw = await device.async_read_raw()
        masks = await device.async_read_masks()
    except ModbusError as err:
        read_error = type(err).__name__
    if raw is not None and (holding := raw.get("holding")) is not None:
        for address in _SERIAL_NUMBER_REGISTERS:
            holding.pop(address, None)

    return async_redact_data(
        {
            "model": device.model,
            "inverter_type": device.inverter_type,
            "serial_number": device.serial_number,
            "readings_components": device.readings_components,
            "settings_components": device.settings_components,
            "active_faults": sorted(fault.key for fault in device.state.active_faults),
            "coordinator_errors": {
                "readings": _last_error(runtime_data.readings),
                "settings": _last_error(runtime_data.settings),
            },
            "address_masks": masks,
            "link": {
                "tuning": asdict(runtime_data.tuner.tuning),
                "stats": asdict(runtime_data.link.stats),
            },
            "read_error": read_error,
            "raw": raw,
        },
        TO_REDACT,
    )
