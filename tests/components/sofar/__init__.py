"""Tests for the Sofar Inverter Modbus integration."""

from __future__ import annotations

from modbus_connection.mock import MockModbusUnit

from homeassistant.components.sofar.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_SERIAL = "SS2ES104N5S445"
MOCK_MODEL = "4.4 KTLX-G3"

MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}


def seed_pv_inverter(unit: MockModbusUnit, serial: str = MOCK_SERIAL) -> None:
    """Seed registers for a PV-only inverter: identify() plus power control."""
    padded = serial.ljust(14, "\x00")
    for i in range(7):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[0x445 + i] = (hi << 8) | lo
    unit.holding[0x0404] = 2  # Running
    unit.holding[0x0484] = 5000  # 50.00 Hz
    unit.holding[0x1105] = 0  # active power control -> nothing armed
