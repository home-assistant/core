"""Diagnostics support for E3/DC."""

from typing import Any

from e3dc_ess_modbus.model import register
from modbus_connection import ModbusError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import HARDWARE_COMPONENTS, POLLED_COMPONENTS, E3dcConfigEntry

TO_REDACT = {"serial_number"}

_SERIAL_NUMBER_REGISTERS = range(register(40036), register(40052))


def _repr_or_none(value: object) -> str | None:
    """Return the repr of ``value``, or None when it is None."""
    return None if value is None else repr(value)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: E3dcConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    The raw registers can be loaded into ``modbus_connection.mock`` to replay a
    problem without the power station. Their keys are Modbus addresses, which
    are one lower than the register numbers in E3/DC's documentation. The serial
    number registers are left out.
    """
    coordinator = entry.runtime_data
    device = coordinator.device
    identity = device.identity
    raw = read_error = None
    try:
        raw = await device.async_read_raw(
            ("identity", *POLLED_COMPONENTS, *HARDWARE_COMPONENTS)
        )
    except ModbusError as err:
        read_error = type(err).__name__
    if raw is not None and (holding := raw.get("holding")) is not None:
        for address in _SERIAL_NUMBER_REGISTERS:
            holding.pop(address, None)
    # Read after the await, so a poll that fails meanwhile matches last_update_success
    last_exception = coordinator.last_exception

    return async_redact_data(
        {
            "manufacturer": identity.manufacturer,
            "model": identity.model,
            "serial_number": identity.serial_number,
            "firmware_release": identity.firmware_release,
            "modbus_version": identity.modbus_version,
            "register_count": identity.register_count,
            "wallboxes": list(device.wallboxes.configured),
            "power_meters": {
                number: meter.meter_type.name
                for number, meter in device.power_meter_readings.items()
                if meter.meter_type is not None and meter.is_installed
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "last_exception": _repr_or_none(last_exception),
                # The cause holds the Modbus errors behind the translated UpdateFailed
                "last_exception_cause": _repr_or_none(
                    last_exception.__cause__ if last_exception is not None else None
                ),
            },
            "read_error": read_error,
            "raw": raw,
        },
        TO_REDACT,
    )
