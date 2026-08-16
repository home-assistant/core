"""Config entry diagnostics.

The raw register map, for an issue report showing exactly what the device
answered.
"""

from typing import Any

from modbus_connection import ModbusError
from sofar_modbus.modern.device import SERIAL_REGISTER, SERIAL_WORDS

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import SofarConfigEntry

# The serial number identifies a specific physical inverter; diagnostics
# files get attached to public GitHub issues, so it's redacted the same way
# the coordinator already keeps it out of logs.
#
# async_redact_data only matches by key name, so it catches the named
# "serial_number" field below but not the same value re-encoded as raw ASCII
# in the "registers" dump -- SERIAL_REGISTER..SERIAL_REGISTER+SERIAL_WORDS
# holds it too (identity block), and the register map is public, so leaving
# it there would trivially defeat the redaction. Stripped separately below.
TO_REDACT = {"serial_number"}

# sofar-modbus's identify() matches a serial against a table of known
# prefixes to resolve the inverter type/model — the longest currently being
# "SP1ES120N6" (10 chars). Keeping that many leading characters in
# `serial_prefix` below is enough to tell which family an *unrecognized*
# serial is closest to (useful for extending that table upstream) without
# keeping the rest of what is otherwise a unique per-device identifier.
_SERIAL_PREFIX_LEN = 10


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SofarConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.device
    served = coordinator.served_components

    # Reads fresh, not coordinator.data, so the dump reflects live register
    # state at download time.
    registers: dict[str, dict[int, int | bool]] = {}
    read_errors: dict[str, str] = {}
    try:
        registers = await device.async_read_raw()
    except ModbusError as err:
        read_errors["device"] = str(err)

    if (holding := registers.get("holding")) is not None:
        for addr in range(SERIAL_REGISTER, SERIAL_REGISTER + SERIAL_WORDS):
            holding.pop(addr, None)

    serial = device.serial_number
    data: dict[str, Any] = {
        "model": device.model,
        "serial_number": serial,
        "serial_prefix": serial[:_SERIAL_PREFIX_LEN] if serial else None,
        "inverter_type": repr(device.inverter_type),
        "served_components": sorted(served),
        "read_errors": read_errors,
        "registers": registers,
    }
    return async_redact_data(data, TO_REDACT)
