"""Tests for the Intesis Modbus integration."""

from modbus_connection.mock import MockModbusUnit

from homeassistant.components.intesis_modbus.const import (
    CONF_BAUDRATE,
    CONF_HAS_VANE,
    CONF_MODEL,
    CONF_TEMPERATURE_FORMAT,
    CONF_UNIT_ID,
)
from homeassistant.const import CONF_DEVICE

INIT_VALUE = 0x8000

MOCK_USER_INPUT = {CONF_DEVICE: "/dev/ttyUSB0", CONF_BAUDRATE: 9600, CONF_UNIT_ID: 1}
MOCK_ENTRY_DATA = {
    **MOCK_USER_INPUT,
    CONF_MODEL: "INMBSMHI001R000",
    CONF_TEMPERATURE_FORMAT: "decicelsius",
    CONF_HAS_VANE: True,
}

# A healthy MHI single-unit gateway, DIP switches on x10 °C.
SINGLE_UNIT_REGISTERS: dict[int, int] = {
    0: 1,  # on
    1: 1,  # heat
    2: 2,  # medium
    3: 10,  # swing
    4: 215,  # setpoint 21.5 °C
    5: 203,  # ambient 20.3 °C
    6: 0,  # window contact closed
    7: 0,  # gateway enabled
    8: 0,  # remote control enabled
    9: 1234,  # operation hours
    10: 0,  # no alarm
    11: 0,  # no error
    13: 30,  # window timeout
    14: 2,  # baud rate code
    15: 1,  # slave address
    21: 4,  # four fan speeds
    22: INIT_VALUE,  # no external temperature
    23: 215,  # real setpoint
    24: 300,  # max setpoint
    25: 160,  # min setpoint
    31: 0,  # window closed
    46: 0,  # remote unlock
    48: 0x0012,  # switch value
    49: 0x0F00,  # MHI device id
    50: 0x0014,  # software version 20
    55: 3,  # undervoltage hours
    60: 125,  # outdoor intake 12.5 °C
    65: INIT_VALUE,  # no input reference
    66: 240,  # return path 24.0 °C
    81: 0,  # error address
    97: 0,  # periodic sendings not blocked
    98: 0,  # slave
}

_IDENTITY = {48, 49, 50}


def seed_single_unit(unit: MockModbusUnit) -> None:
    """Seed a healthy single-unit gateway."""
    for address, value in SINGLE_UNIT_REGISTERS.items():
        unit.holding[address] = value


def seed_initialising_single_unit(unit: MockModbusUnit) -> None:
    """Seed a single-unit gateway that is still initialising."""
    for address, value in SINGLE_UNIT_REGISTERS.items():
        unit.holding[address] = value if address in _IDENTITY else INIT_VALUE
    unit.holding[11] = 65532
