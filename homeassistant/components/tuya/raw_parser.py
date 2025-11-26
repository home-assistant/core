"""Parsers for RAW (base64-encoded bytes) values."""

from dataclasses import dataclass
import struct
from typing import Self


@dataclass(kw_only=True)
class ElectricityValue:
    """Electricity RAW value."""

    current: float
    power: float
    voltage: float

    @classmethod
    def from_bytes(cls, raw: bytes) -> Self | None:
        """Parse bytes and return an ElectricityValue object."""

        if len(raw) >= 8:
            voltage = struct.unpack(">H", raw[0:2])[0] / 10.0
            current = struct.unpack(">L", b"\x00" + raw[2:5])[0]
            power = struct.unpack(">L", b"\x00" + raw[5:8])[0]
            return cls(current=current, power=power, voltage=voltage)

        return None
