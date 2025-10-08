"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
import json
import struct
from typing import Any, Self

from tuya_sharing import CustomerDevice

from .const import DPCode
from .util import remap_value

type StateConversionFunction = Callable[
    [CustomerDevice, EnumTypeData | IntegerTypeData | None, Any], Any
]


@dataclass
class IntegerTypeData:
    """Integer Type Data."""

    dpcode: DPCode
    min: int
    max: int
    scale: float
    step: float
    unit: str | None = None
    type: str | None = None

    @property
    def max_scaled(self) -> float:
        """Return the max scaled."""
        return self.scale_value(self.max)

    @property
    def min_scaled(self) -> float:
        """Return the min scaled."""
        return self.scale_value(self.min)

    @property
    def step_scaled(self) -> float:
        """Return the step scaled."""
        return self.step / (10**self.scale)

    def scale_value(self, value: float) -> float:
        """Scale a value."""
        return value / (10**self.scale)

    def scale_value_back(self, value: float) -> int:
        """Return raw value for scaled."""
        return int(value * (10**self.scale))

    def remap_value_to(
        self,
        value: float,
        to_min: float = 0,
        to_max: float = 255,
        reverse: bool = False,
    ) -> float:
        """Remap a value from this range to a new range."""
        return remap_value(value, self.min, self.max, to_min, to_max, reverse)

    def remap_value_from(
        self,
        value: float,
        from_min: float = 0,
        from_max: float = 255,
        reverse: bool = False,
    ) -> float:
        """Remap a value from its current range to this range."""
        return remap_value(value, from_min, from_max, self.min, self.max, reverse)

    @classmethod
    def from_json(cls, dpcode: DPCode, data: str) -> IntegerTypeData | None:
        """Load JSON string and return a IntegerTypeData object."""
        if not (parsed := json.loads(data)):
            return None

        return cls(
            dpcode,
            min=int(parsed["min"]),
            max=int(parsed["max"]),
            scale=float(parsed["scale"]),
            step=max(float(parsed["step"]), 1),
            unit=parsed.get("unit"),
            type=parsed.get("type"),
        )


@dataclass
class EnumTypeData:
    """Enum Type Data."""

    dpcode: DPCode
    range: list[str]

    @classmethod
    def from_json(cls, dpcode: DPCode, data: str) -> EnumTypeData | None:
        """Load JSON string and return a EnumTypeData object."""
        if not (parsed := json.loads(data)):
            return None
        return cls(dpcode, **parsed)


class ComplexValue:
    """Complex value (for JSON/RAW parsing)."""

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Load JSON string and return a ComplexValue object."""
        raise NotImplementedError("from_json is not implemented for this type")

    @classmethod
    def from_raw(cls, data: str) -> Self | None:
        """Decode base64 string and return a ComplexValue object."""
        raise NotImplementedError("from_raw is not implemented for this type")


@dataclass
class ElectricityValue(ComplexValue):
    """Electricity complex value."""

    electriccurrent: str | None = None
    power: str | None = None
    voltage: str | None = None

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Load JSON string and return a ElectricityValue object."""
        return cls(**json.loads(data.lower()))

    @classmethod
    def from_raw(cls, data: str) -> Self | None:
        """Decode base64 string and return a ElectricityValue object."""
        raw = base64.b64decode(data)
        if len(raw) == 0:
            return None
        voltage = struct.unpack(">H", raw[0:2])[0] / 10.0
        electriccurrent = struct.unpack(">L", b"\x00" + raw[2:5])[0] / 1000.0
        power = struct.unpack(">L", b"\x00" + raw[5:8])[0] / 1000.0
        return cls(
            electriccurrent=str(electriccurrent), power=str(power), voltage=str(voltage)
        )
