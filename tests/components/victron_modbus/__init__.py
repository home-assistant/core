"""Tests for the Victron Modbus integration."""

from modbus_connection.encode import encode_string

SERIAL = "HQ2345ABCDE"
OTHER_SERIAL = "HQ9999ZZZZZ"
VM_3P75CT = 0xA1B1
P1LINK = 0xC02F


def set_identity(unit, product_id: int, serial: str = SERIAL) -> None:
    """Make the fake unit identify as a product with a serial number."""
    unit.holding[0x1000] = product_id
    unit.holding[0x1001] = encode_string(serial, length=8)
    unit.holding[0x100B] = 3
    unit.holding[0x2000] = 3  # phase configuration: three-phase


def _words(value: int) -> list[int]:
    """A 32-bit value as two big-endian registers (negative as two's complement)."""
    value &= 0xFFFFFFFF
    return [value >> 16, value & 0xFFFF]


def set_readings(unit) -> None:
    """Fill the fake unit with a plausible reading for every register."""
    unit.holding[0x3032] = 5001  # frequency: 50.01 Hz
    unit.holding[0x303E] = 50012  # fine frequency: 50.012 Hz
    unit.holding[0x3033] = 12  # PE-N voltage: 0.12 V
    unit.holding[0x3034] = _words(1234567)  # total forward energy: 12345.67 kWh
    unit.holding[0x3036] = _words(765432)  # total reverse energy: 7654.32 kWh
    unit.holding[0x3080] = _words(-1000)  # total power: -1000 W
    for phase in range(3):
        unit.holding[0x3040 + 8 * phase] = 23010 + phase  # voltage: 230.1x V
        unit.holding[0x3041 + 8 * phase] = 410 + phase  # 16-bit current: 4.1x A
        unit.holding[0x3042 + 8 * phase] = _words(400000 + phase)  # 4000.0x kWh
        unit.holding[0x3044 + 8 * phase] = _words(250000 + phase)  # 2500.0x kWh
        unit.holding[0x3058 + 2 * phase] = _words(420 + phase)  # 32-bit current: 4.2x A
        unit.holding[0x3082 + 4 * phase] = _words(-350 + phase)  # power: -35x W
