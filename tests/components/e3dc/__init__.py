"""Tests for the E3/DC integration."""

from e3dc_ess_modbus.model import register
from modbus_connection.mock import MockModbusUnit

from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_SERIAL = "S10-12345678912"
MOCK_MODEL = "S10 X"
MOCK_TITLE = f"E3/DC {MOCK_MODEL}"
MOCK_FIRMWARE = "S10_2026_04"

MOCK_ENTRY_DATA = {CONF_HOST: "192.168.1.100", CONF_PORT: 502}


def _ascii_words(text: str, length: int) -> list[int]:
    """Pack ASCII into ``length`` registers, two characters each."""
    padded = text.ljust(length * 2, "\0")
    return [(ord(padded[i]) << 8) | ord(padded[i + 1]) for i in range(0, length * 2, 2)]


def int32_words(value: int) -> list[int]:
    """An int32 as E3/DC sends it, low word first."""
    raw = value & 0xFFFFFFFF
    return [raw & 0xFFFF, raw >> 16]


def seed(unit: MockModbusUnit, holding: dict[int, int | list[int]]) -> None:
    """Load register values, given by the manual's numbering, into the mock."""
    for index, value in holding.items():
        unit.holding[register(index)] = value


def seed_identity(
    unit: MockModbusUnit, serial: str = MOCK_SERIAL, model: str = MOCK_MODEL
) -> None:
    """Seed the identification block: every firmware has it."""
    seed(
        unit,
        {
            40001: 0xE3DC,  # Marker for the E3/DC protocol
            40002: 0x0203,  # Modbus protocol version 2.3
            40003: 210,  # Number of registers the power station serves
            40004: _ascii_words("HagerEnergy GmbH", 16),  # Manufacturer
            40020: _ascii_words(model, 16),  # Model
            40036: _ascii_words(serial, 16),  # Serial number
            40052: _ascii_words(MOCK_FIRMWARE, 16),  # Firmware release
        },
    )


def seed_power_station(unit: MockModbusUnit) -> None:
    """Seed an S10 X with its identity and power flows."""
    seed_identity(unit)
    seed(
        unit,
        {
            # PV and the additional feeder supply what the battery, house, wallbox
            # and grid take
            40068: int32_words(5321),  # PV power
            40070: int32_words(1200),  # Battery power, charging
            40072: int32_words(870),  # House power
            40074: int32_words(-600),  # Grid power, feeding in
            40076: int32_words(300),  # Additional feeder power
            40078: int32_words(2951),  # Wallbox power
            40080: int32_words(2951),  # Wallbox solar power
            40082: (100 << 8) | 89,  # Self-sufficiency 100 %, self-consumption 89 %
            40083: 87,  # Battery state of charge, in %
            40084: 2,  # Emergency power not active
            40085: 0b0000100,  # EMS status: emergency power ready
            40088: 0b1,  # Wallbox 0 available
            40105: 1,  # Power meter 0 at the grid connection point
            40109: 2,  # Power meter 1 measures an additional feeder
        },
    )
