"""Diagnostics for KACO Modbus."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import KacoConfigEntry

TO_REDACT = {"serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: KacoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw register map is included because it loads straight into
    ``modbus_connection.mock``, which reproduces a reported problem without
    the hardware. It covers the polled components only, so the serial number
    model 1 holds in the clear is not in it.
    """
    coordinator = entry.runtime_data
    device = coordinator.device
    info = device.info
    assert info is not None

    return async_redact_data(
        {
            "manufacturer": info.manufacturer,
            "model": info.model,
            "firmware": info.firmware,
            "options": info.options,
            "serial_number": info.serial_number,
            "base_address": device.base_address,
            "models": sorted(device.models or ()),
            "strings": len(device.strings),
            "updated": sorted(coordinator.data.updated),
            "failed": {
                component: str(error)
                for component, error in coordinator.data.failed.items()
            },
            "raw": await device.async_read_raw(),
        },
        TO_REDACT,
    )
