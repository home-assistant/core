"""Tests for the De Dietrich integration."""

from modbus_connection.mock import MockModbusUnit

from homeassistant.components.de_dietrich.const import (
    CONF_SYSTEM,
    CONF_UNIT_ID,
    DEFAULT_UNIT_ID,
    SYSTEM_ISYSTEM,
)
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_TITLE = "De Dietrich"
MOCK_ENTRY_ID = "01K5G6X6VZXZ9GJ2YFVZ2VE9RB"

MOCK_USER_INPUT = {
    CONF_HOST: "192.168.1.50",
    CONF_PORT: 502,
    CONF_UNIT_ID: DEFAULT_UNIT_ID,
    CONF_SYSTEM: SYSTEM_ISYSTEM,
}


def seed_boiler(unit: MockModbusUnit, boiler_type: int = 24) -> None:
    """Seed just enough for the probe to succeed: a recognized boiler-type code."""
    unit.holding[457] = boiler_type


def seed_isystem_boiler(unit: MockModbusUnit) -> None:
    """Seed a DiematicISystem boiler with canned sensor and identity values."""
    seed_boiler(unit)
    unit.holding[600] = 100  # software_version
    unit.holding[601] = 50  # outdoor_temp -> 5.0 °C
    unit.holding[602] = 600  # boiler_temp -> 60.0 °C
    unit.holding[603] = 450  # hot_water.temp -> 45.0 °C
    unit.holding[604] = 1200  # smoke_temp -> 120.0 °C
    unit.holding[607] = 550  # return_temp -> 55.0 °C
    unit.holding[608] = 35  # ionization_current -> 3.5 µA
    unit.holding[609] = 2500  # fan_speed -> 2500 rpm
    unit.holding[610] = 15  # water_pressure -> 1.5 bar
    unit.holding[614] = 210  # circuit_a.room_temp -> 21.0 °C
    unit.holding[616] = 205  # circuit_b.room_temp -> 20.5 °C
    unit.holding[620] = 650  # calc_boiler_temp -> 65.0 °C
