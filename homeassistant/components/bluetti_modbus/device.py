"""The device object shared by setup and the config flow."""

from bluetti_modbus_lib import (
    AGGREGATE_SUMMARY_FIELDS,
    Balco260,
    aggregate_pack_summary_component,
)
from modbus_connection import ModbusUnit

from .const import EXCLUDED_FIELDS, SETTINGS_FIELDS


def restricted_device(unit: ModbusUnit) -> Balco260:
    """Return the power station with EXCLUDED_FIELDS left out of its read plan.

    Used for the config flow's probe as well as for setup, so both read the
    same registers. The settings are read on their own poll. The pack summary
    is left out too: it reads 0 at the device's own unit ID.
    """
    device = Balco260(unit)
    left_out = EXCLUDED_FIELDS | SETTINGS_FIELDS | AGGREGATE_SUMMARY_FIELDS
    device.restrict_fields(
        name for name in device.field_names() if name not in left_out
    )
    return device


def bms_device(unit: ModbusUnit) -> Balco260:
    """Return the power station restricted to its battery's BMS version.

    Read once at setup: it only goes into the device's software version.
    """
    device = Balco260(unit)
    device.restrict_fields({"b_ver_count", "b_ver_1"})
    return device


def pack_summary(unit: ModbusUnit) -> Balco260:
    """Return the pack summary read at the aggregate unit ID, 250.

    It covers every battery pack attached, the built-in one included. The
    whole block is read, in one request, including the fields without an
    entity.
    """
    return aggregate_pack_summary_component(unit)
