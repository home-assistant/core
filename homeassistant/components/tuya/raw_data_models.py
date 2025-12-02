"""Parsers for RAW (base64-encoded bytes) values."""

from dataclasses import dataclass
import struct
from typing import Self


@dataclass(kw_only=True)
class ElectricityData:
    """Electricity RAW value."""

    current: float
    power: float
    voltage: float

    @classmethod
    def from_bytes(cls, raw: bytes) -> Self | None:
        """Parse bytes and return an ElectricityValue object."""
        # Format:
        # - legacy: 8 bytes
        # - v01: [ver=0x01][len=0x0F][data(15 bytes)]
        # - v02: [ver=0x02][len=0x0F][data(15 bytes)][sign_bitmap(1 byte)]
        # Data layout (big-endian):
        # - voltage: 2B, unit 0.1 V
        # - current: 3B, unit 0.001 A (i.e., mA)
        # - active power: 3B, unit 0.001 kW (i.e., W)
        # - reactive power: 3B, unit 0.001 kVar
        # - apparent power: 3B, unit 0.001 kVA
        # - power factor: 1B, unit 0.01
        # Sign bitmap (v02 only, 1 bit means negative):
        # - bit0 current
        # - bit1 active power
        # - bit2 reactive
        # - bit3 power factor

        is_v1 = len(raw) == 17 and raw[0:2] == b"\x01\x0f"
        is_v2 = len(raw) == 18 and raw[0:2] == b"\x02\x0f"
        if is_v1 or is_v2:
            data = raw[2:17]

            voltage = struct.unpack(">H", data[0:2])[0] / 10.0
            current = struct.unpack(">L", b"\x00" + data[2:5])[0]
            power = struct.unpack(">L", b"\x00" + data[5:8])[0]

            if is_v2:
                sign_bitmap = raw[17]
                if sign_bitmap & 0x01:
                    current = -current
                if sign_bitmap & 0x02:
                    power = -power

            return cls(current=current, power=power, voltage=voltage)

        if len(raw) >= 8:
            voltage = struct.unpack(">H", raw[0:2])[0] / 10.0
            current = struct.unpack(">L", b"\x00" + raw[2:5])[0]
            power = struct.unpack(">L", b"\x00" + raw[5:8])[0]
            return cls(current=current, power=power, voltage=voltage)

        return None
