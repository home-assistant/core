"""The device object shared by setup and the config flow."""

from bluetti_modbus_lib.base_devices.bluetti_device import BluettiDevice
from bluetti_modbus_lib.devices.getter import get_device
from modbus_connection import ModbusUnit

from .const import DEVICE_TYPE_BALCO260, EXCLUDED_FIELDS


def restricted_device(unit: ModbusUnit) -> BluettiDevice:
    """Return the power station with EXCLUDED_FIELDS left out of its read plan.

    Used for the config flow's probe as well as for setup, so both read the
    same registers.
    """
    device = get_device(DEVICE_TYPE_BALCO260, unit)
    assert device is not None  # DEVICE_TYPE_BALCO260 is always a known device type
    device.restrict_fields(
        name for name in device.field_names() if name not in EXCLUDED_FIELDS
    )
    return device
