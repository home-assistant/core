"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import struct
from typing import Literal, Self, overload

from tuya_sharing import CustomerDevice

from .const import DPCode, DPType
from .util import remap_value

_DPTYPE_MAPPING: dict[str, DPType] = {
    "bitmap": DPType.BITMAP,
    "bool": DPType.BOOLEAN,
    "enum": DPType.ENUM,
    "json": DPType.JSON,
    "raw": DPType.RAW,
    "string": DPType.STRING,
    "value": DPType.INTEGER,
}


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


class ComplexTypeData:
    """Complex Type Data (for JSON/RAW parsing)."""

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Load JSON string and return a ComplexTypeData object."""
        raise NotImplementedError("from_json is not implemented for this type")

    @classmethod
    def from_raw(cls, data: str) -> Self:
        """Decode base64 string and return a ComplexTypeData object."""
        raise NotImplementedError("from_raw is not implemented for this type")


@dataclass
class ElectricityTypeData(ComplexTypeData):
    """Electricity Type Data."""

    electriccurrent: str | None = None
    power: str | None = None
    voltage: str | None = None

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Load JSON string and return a ElectricityTypeData object."""
        return cls(**json.loads(data.lower()))

    @classmethod
    def from_raw(cls, data: str) -> Self:
        """Decode base64 string and return a ElectricityTypeData object."""
        raw = base64.b64decode(data)
        voltage = struct.unpack(">H", raw[0:2])[0] / 10.0
        electriccurrent = struct.unpack(">L", b"\x00" + raw[2:5])[0] / 1000.0
        power = struct.unpack(">L", b"\x00" + raw[5:8])[0] / 1000.0
        return cls(
            electriccurrent=str(electriccurrent), power=str(power), voltage=str(voltage)
        )


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | DPCode | tuple[DPCode, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: Literal[DPType.ENUM],
) -> EnumTypeData | None: ...


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | DPCode | tuple[DPCode, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: Literal[DPType.INTEGER],
) -> IntegerTypeData | None: ...


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | DPCode | tuple[DPCode, ...] | None,
    *,
    prefer_function: bool = False,
) -> DPCode | None: ...


def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | DPCode | tuple[DPCode, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: DPType | None = None,
) -> DPCode | EnumTypeData | IntegerTypeData | None:
    """Find a matching DP code available on for this device."""
    if dpcodes is None:
        return None

    if isinstance(dpcodes, str):
        dpcodes = (DPCode(dpcodes),)
    elif not isinstance(dpcodes, tuple):
        dpcodes = (dpcodes,)

    order = ["status_range", "function"]
    if prefer_function:
        order = ["function", "status_range"]

    # When we are not looking for a specific datatype, we can append status for
    # searching
    if not dptype:
        order.append("status")

    for dpcode in dpcodes:
        for key in order:
            if dpcode not in getattr(device, key):
                continue
            if (
                dptype == DPType.ENUM
                and getattr(device, key)[dpcode].type == DPType.ENUM
            ):
                if not (
                    enum_type := EnumTypeData.from_json(
                        dpcode, getattr(device, key)[dpcode].values
                    )
                ):
                    continue
                return enum_type

            if (
                dptype == DPType.INTEGER
                and getattr(device, key)[dpcode].type == DPType.INTEGER
            ):
                if not (
                    integer_type := IntegerTypeData.from_json(
                        dpcode, getattr(device, key)[dpcode].values
                    )
                ):
                    continue
                return integer_type

            if dptype not in (DPType.ENUM, DPType.INTEGER):
                return dpcode

    return None


def get_dptype(
    self, dpcode: DPCode | None, prefer_function: bool = False
) -> DPType | None:
    """Find a matching DPCode data type available on for this device."""
    if dpcode is None:
        return None

    order = ["status_range", "function"]
    if prefer_function:
        order = ["function", "status_range"]
    for key in order:
        if dpcode in getattr(self.device, key):
            current_type = getattr(self.device, key)[dpcode].type
            try:
                return DPType(current_type)
            except ValueError:
                # Sometimes, we get ill-formed DPTypes from the cloud,
                # this fixes them and maps them to the correct DPType.
                return _DPTYPE_MAPPING.get(current_type)

    return None
