"""The device object shared by setup and the config flow."""

from bluetti_modbus_lib import (
    AGGREGATE_SUMMARY_FIELDS,
    Balco260,
    aggregate_pack_summary_component,
)
from modbus_connection import ModbusUnit

from .const import EXCLUDED_FIELDS


def restricted_device(unit: ModbusUnit) -> Balco260:
    """Return the power station with EXCLUDED_FIELDS left out of its read plan.

    Used for the config flow's probe as well as for setup, so both read the
    same registers. The pack summary is left out too: it reads 0 at the
    device's own unit ID.
    """
    device = Balco260(unit)
    device.restrict_fields(
        name
        for name in device.field_names()
        if name not in EXCLUDED_FIELDS and name not in AGGREGATE_SUMMARY_FIELDS
    )
    return device


def pack_summary(unit: ModbusUnit) -> Balco260:
    """Return the pack summary read at the aggregate unit ID, 250.

    It covers every battery pack attached, the built-in one included. The
    whole block is read, in one request, including the fields without an
    entity.
    """
    return aggregate_pack_summary_component(unit)
