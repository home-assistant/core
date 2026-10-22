"""Diagnostics support for Victron Modbus."""

from typing import Any

from modbus_connection import ModbusError

from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant

from .coordinator import VictronModbusConfigEntry

# The serial number (0x1001-0x1008) identifies the owner's device.
_SERIAL_REGISTERS = range(0x1001, 0x1009)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: VictronModbusConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry: the last polls and the raw registers."""
    data = entry.runtime_data
    try:
        raw = await data.power.device.async_read_raw()
    except ModbusError as err:
        registers: dict[str, Any] = {"error": repr(err)}
    else:
        registers = {
            space: {
                address: value
                for address, value in values.items()
                if space != "holding" or address not in _SERIAL_REGISTERS
            }
            for space, values in raw.items()
        }
    return {
        "model": entry.data[CONF_MODEL],
        "polls": {
            name: {
                "updated": sorted(coordinator.data.updated),
                "failed": {
                    sub_system: repr(err)
                    for sub_system, err in coordinator.data.failed.items()
                },
            }
            for name, coordinator in (
                ("power", data.power),
                ("readings", data.readings),
            )
        },
        "registers": registers,
    }
