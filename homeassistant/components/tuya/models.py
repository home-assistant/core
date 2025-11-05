"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import struct
from typing import Any, Literal, Self, overload

from tuya_sharing import CustomerDevice

from tuya_sharing import CustomerDevice

from .const import DPCode, DPType
from .util import remap_value


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


def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | DPCode | tuple[DPCode, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: DPType,
) -> EnumTypeData | IntegerTypeData | None:
    """Find type information for a matching DP code available for this device."""
    if dptype not in (DPType.ENUM, DPType.INTEGER):
        raise NotImplementedError("Only ENUM and INTEGER types are supported")

    if dpcodes is None:
        return None

    if isinstance(dpcodes, str):
        dpcodes = (DPCode(dpcodes),)
    elif not isinstance(dpcodes, tuple):
        dpcodes = (dpcodes,)

    lookup_tuple = (
        (device.function, device.status_range)
        if prefer_function
        else (device.status_range, device.function)
    )

    for dpcode in dpcodes:
        for device_specs in lookup_tuple:
            if not (
                (current_definition := device_specs.get(dpcode))
                and current_definition.type == dptype
            ):
                continue
            if dptype is DPType.ENUM:
                if not (
                    enum_type := EnumTypeData.from_json(
                        dpcode, current_definition.values
                    )
                ):
                    continue
                return enum_type
            if dptype is DPType.INTEGER:
                if not (
                    integer_type := IntegerTypeData.from_json(
                        dpcode, current_definition.values
                    )
                ):
                    continue
                return integer_type

    return None


@dataclass(kw_only=True)
class DeviceDataParser:
    """Device Data Parser."""

    dpcode: str

    def _read_device_value_raw(self, device: CustomerDevice) -> Any | None:
        """Read the device value for the dpcode."""
        return device.status.get(self.dpcode)

    def read_device_value(self, device: CustomerDevice) -> Any | None:
        """Read the device value for the dpcode."""
        raise NotImplementedError


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
class EnumTypeData(DeviceDataParser):
    """Enum Type Data."""

    range: list[str]

    def read_device_value(self, device: CustomerDevice) -> str | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_device_value_raw(device)) in self.range:
            return raw_value
        return None

    @classmethod
    def from_json(cls, dpcode: DPCode, data: str) -> EnumTypeData | None:
        """Load JSON string and return a EnumTypeData object."""
        if not (parsed := json.loads(data)):
            return None
        return cls(dpcode=dpcode, **parsed)


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
