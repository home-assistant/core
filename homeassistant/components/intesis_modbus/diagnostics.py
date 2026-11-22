"""Diagnostics support for Intesis Modbus gateways."""

from typing import Any

from modbus_connection import ModbusError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .coordinator import IntesisConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IntesisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw register map is included because it loads straight into
    ``modbus_connection.mock``, which reproduces a reported problem without
    the hardware.
    """
    diagnostics: dict[str, Any] = {
        "entry": dict(entry.data),
        "options": dict(entry.options),
        "state": entry.state.value,
        "updated": None,
        "failed": None,
        "read_error": None,
        "registers": None,
    }
    # An entry that is not set up, one waiting to retry included, has no
    # coordinator: the download then says so instead of failing.
    if entry.state is not ConfigEntryState.LOADED:
        return diagnostics
    coordinator = entry.runtime_data
    # The most recent poll, also when it failed; none if nothing answered
    if (report := coordinator.last_report) is not None:
        diagnostics["updated"] = sorted(report.updated)
        diagnostics["failed"] = {name: str(err) for name, err in report.failed.items()}
    try:
        diagnostics["registers"] = await coordinator.device.async_read_raw()
    except ModbusError as err:
        diagnostics["read_error"] = type(err).__name__
    return diagnostics
