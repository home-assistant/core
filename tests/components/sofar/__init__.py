"""Tests for the Sofar Inverter Modbus integration."""

from modbus_connection.mock import MockModbusUnit

from homeassistant.components.sofar.const import CONF_UNIT_ID
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_SERIAL = "SS2ES104N5S445"
MOCK_MODEL = "4.4 KTLX-G3"
MOCK_HYBRID_SERIAL = "SP1XXES100XX"
MOCK_HYBRID_MODEL = "HYDxxKTL-3P"

MOCK_HW_VERSION = "V100"
MOCK_SW_VERSION = "V220"

MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: 502,
    CONF_UNIT_ID: 1,
}


def _seed_string(unit: MockModbusUnit, address: int, words: int, text: str) -> None:
    """Encode ASCII across consecutive registers, two characters each."""
    padded = text.ljust(words * 2, "\x00")
    for i in range(words):
        hi, lo = ord(padded[2 * i]), ord(padded[2 * i + 1])
        unit.holding[address + i] = (hi << 8) | lo


def _seed_common(unit: MockModbusUnit, serial: str) -> None:
    """Seed identity, run state and grid frequency: every model has these."""
    _seed_string(unit, 0x0445, 7, serial)
    _seed_string(unit, 0x044D, 2, MOCK_HW_VERSION)
    _seed_string(unit, 0x044F, 4, MOCK_SW_VERSION)
    unit.holding[0x0404] = 2  # Running
    unit.holding[0x0484] = 5000  # 50.00 Hz


def seed_pv_inverter(unit: MockModbusUnit, serial: str = MOCK_SERIAL) -> None:
    """Seed a PV-only inverter: identify(), power control, PV strings."""
    _seed_common(unit, serial)
    unit.holding[0x1105] = 0  # active power control -> nothing armed
    unit.holding[0x0586] = 250  # pv_power_1 -> 2.5 kW
    unit.holding[0x0589] = 180  # pv_power_2 -> 1.8 kW
    unit.holding[0x05C4] = 43  # pv_power_total -> 4.3 kW
    unit.holding[0x0686] = 0  # solar_generation_total high word
    unit.holding[0x0687] = 150  # solar_generation_total low word -> 15.0 kWh
    unit.holding[0x0684] = 0  # solar_generation_today high word
    unit.holding[0x0685] = 1000  # solar_generation_today low word -> 10.0 kWh


def seed_hybrid_inverter(
    unit: MockModbusUnit, serial: str = MOCK_HYBRID_SERIAL
) -> None:
    """Seed a hybrid inverter with battery packs 1 and 3 wired, 2 absent."""
    _seed_common(unit, serial)
    unit.holding[0x0604] = 520  # battery_voltage_1 -> 52.0 V
    unit.holding[0x0608] = 87  # battery_capacity_1 -> 87%
    unit.holding[0x0612] = 515  # battery_voltage_3 -> 51.5 V
    unit.holding[0x0616] = 85  # battery_capacity_3 -> 85%
