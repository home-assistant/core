"""The device object shared by setup and the config flow."""

from bluetti_modbus_lib import Balco260
from modbus_connection import ModbusUnit

from .const import EXCLUDED_FIELDS, SETTINGS_FIELDS


def restricted_device(unit: ModbusUnit) -> Balco260:
    """Return the power station with EXCLUDED_FIELDS left out of its read plan.

    Used for the config flow's probe as well as for setup, so both read the
    same registers. The settings are read on their own poll.
    """
    device = Balco260(unit)
    device.restrict_fields(
        name
        for name in device.field_names()
        if name not in EXCLUDED_FIELDS and name not in SETTINGS_FIELDS
    )
    return device


def bms_device(unit: ModbusUnit) -> Balco260:
    """Return the power station restricted to its battery's BMS version.

    Read once at setup: it only goes into the device's software version.
    """
    device = Balco260(unit)
    device.restrict_fields({"b_ver_count", "b_ver_1"})
    return device
