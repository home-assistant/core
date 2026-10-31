"""Diagnostics support for the BLUETTI Modbus integration."""

from typing import Any

from bluetti_modbus_lib import Balco260
from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import BluettiModbusConfigEntry

TO_REDACT = {"d_serial"}

# The device's own serial and those of its battery pack and IoT module, also
# the ones this integration does not poll, should its read plan grow.
SERIAL_ADDRESSES = frozenset(
    address
    for field in (Balco260.d_serial, Balco260.b_serial, Balco260.d_iot_serial)
    for address in range(field.address, field.address + field.count)
)


async def _async_raw_registers(device: Balco260) -> dict[str, Any]:
    """Read the device's registers, leaving out every serial number."""
    try:
        raw = await device.async_read_raw(notify=False)
    except ModbusError as err:
        return {"raw": None, "raw_error": str(err)}
    return {
        "raw": {
            space: {
                address: value
                for address, value in registers.items()
                if address not in SERIAL_ADDRESSES
            }
            for space, registers in raw.items()
        },
        "raw_error": None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BluettiModbusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw registers load straight into ``modbus_connection.mock``, which
    reproduces a reported problem without the hardware. Every register a
    serial number lives in is left out of them.
    """
    coordinator = entry.runtime_data.coordinator
    settings = entry.runtime_data.settings
    return {
        "last_update_success": coordinator.last_update_success,
        "values": async_redact_data(coordinator.data, TO_REDACT),
        **await _async_raw_registers(coordinator.device),
        "settings": {
            "last_update_success": settings.last_update_success,
            # None when the settings could not be read at setup.
            "values": async_redact_data(settings.data, TO_REDACT),
            **await _async_raw_registers(settings.device),
        },
    }
