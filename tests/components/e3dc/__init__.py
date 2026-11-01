"""Tests for the E3/DC integration."""

from e3dc_ess_modbus.model import register
from modbus_connection.mock import MockModbusUnit

from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_SERIAL = "S10-12345678912"
MOCK_MODEL = "S10 X"
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
            40001: 0xE3DC,
            40002: 0x0203,
            40003: 210,
            40004: _ascii_words("HagerEnergy GmbH", 16),
            40020: _ascii_words(model, 16),
            40036: _ascii_words(serial, 16),
            40052: _ascii_words(MOCK_FIRMWARE, 16),
        },
    )


def seed_power_station(unit: MockModbusUnit) -> None:
    """Seed an S10 X with one wallbox, a root meter and every firmware block."""
    seed_identity(unit)
    seed(
        unit,
        {
            40068: int32_words(5321),
            40070: int32_words(-1200),
            40072: int32_words(870),
            40074: int32_words(-600),
            40078: int32_words(11000),
            40080: int32_words(4200),
            40082: 6738,  # self-sufficiency 26 %, self-consumption 82 %
            40083: 87,
            40084: 2,  # emergency power not active
            40085: 0b0010100,  # emergency power ready, feed-in limited
            40088: 0b0000000111011,  # wallbox 0: solar, charging, plugged, locked
            40096: 612,
            40099: 450,
            40102: 2754,
            40105: 1,  # meter 0: root
            40106: 0xFF38,
            40107: 150,
            40108: 100,
            40109: 6,  # meter 1: not used
            40137: 1,
            40138: int32_words(-200),
            40140: int32_words(150),
            40142: int32_words(100),
            40186: int32_words(5000),
            40188: 1,
            40194: 30,
            40196: 30,
            40201: 0,
            40202: int32_words(9000),
            40204: int32_words(-9000),
            40206: int32_words(7800),
            40208: int32_words(10500),
            41006: int32_words(1750),
            41018: 2301,
            41019: 2299,
            41020: 2310,
            41024: 5001,
            41025: 2754,
            41027: 1210,
        },
    )
