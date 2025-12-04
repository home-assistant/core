"""Tuya Home Assistant type information classes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Self, cast, overload

from tuya_sharing import CustomerDevice

from homeassistant.util.json import json_loads_object

from .const import DPType
from .util import parse_dptype, remap_value


@dataclass(kw_only=True)
class TypeInformation:
    """Type information.

    As provided by the SDK, from `device.function` / `device.status_range`.
    """

    dpcode: str
    type_data: str | None = None

    @classmethod
    def from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a TypeInformation object."""
        return cls(dpcode=dpcode, type_data=type_data)


@dataclass(kw_only=True)
class BitmapTypeInformation(TypeInformation):
    """Bitmap type information."""

    label: list[str]

    @classmethod
    def from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a BitmapTypeInformation object."""
        if not (parsed := json_loads_object(type_data)):
            return None
        return cls(
            dpcode=dpcode,
            type_data=type_data,
            **cast(dict[str, list[str]], parsed),
        )


@dataclass(kw_only=True)
class EnumTypeInformation(TypeInformation):
    """Enum type information."""

    range: list[str]

    @classmethod
    def from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a EnumTypeInformation object."""
        if not (parsed := json_loads_object(type_data)):
            return None
        return cls(
            dpcode=dpcode,
            type_data=type_data,
            **cast(dict[str, list[str]], parsed),
        )


@dataclass(kw_only=True)
class IntegerTypeInformation(TypeInformation):
    """Integer type information."""

    min: int
    max: int
    scale: int
    step: int
    unit: str | None = None

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

    def scale_value(self, value: int) -> float:
        """Scale a value."""
        return value / (10**self.scale)

    def scale_value_back(self, value: float) -> int:
        """Return raw value for scaled."""
        return round(value * (10**self.scale))

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
    def from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a IntegerTypeInformation object."""
        if not (parsed := cast(dict[str, Any] | None, json_loads_object(type_data))):
            return None

        return cls(
            dpcode=dpcode,
            type_data=type_data,
            min=int(parsed["min"]),
            max=int(parsed["max"]),
            scale=int(parsed["scale"]),
            step=int(parsed["step"]),
            unit=parsed.get("unit"),
        )


_TYPE_INFORMATION_MAPPINGS: dict[DPType, type[TypeInformation]] = {
    DPType.BITMAP: BitmapTypeInformation,
    DPType.BOOLEAN: TypeInformation,
    DPType.ENUM: EnumTypeInformation,
    DPType.INTEGER: IntegerTypeInformation,
    DPType.JSON: TypeInformation,
    DPType.RAW: TypeInformation,
    DPType.STRING: TypeInformation,
}


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | tuple[str, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: Literal[DPType.BITMAP],
) -> BitmapTypeInformation | None: ...


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | tuple[str, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: Literal[DPType.ENUM],
) -> EnumTypeInformation | None: ...


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | tuple[str, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: Literal[DPType.INTEGER],
) -> IntegerTypeInformation | None: ...


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | tuple[str, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: Literal[DPType.BOOLEAN, DPType.JSON, DPType.RAW],
) -> TypeInformation | None: ...


def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | tuple[str, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: DPType,
) -> TypeInformation | None:
    """Find type information for a matching DP code available for this device."""
    if not (type_information_cls := _TYPE_INFORMATION_MAPPINGS.get(dptype)):
        raise NotImplementedError(f"find_dpcode not supported for {dptype}")

    if dpcodes is None:
        return None

    if not isinstance(dpcodes, tuple):
        dpcodes = (dpcodes,)

    lookup_tuple = (
        (device.function, device.status_range)
        if prefer_function
        else (device.status_range, device.function)
    )

    for dpcode in dpcodes:
        for device_specs in lookup_tuple:
            if (
                (current_definition := device_specs.get(dpcode))
                and parse_dptype(current_definition.type) is dptype
                and (
                    type_information := type_information_cls.from_json(
                        dpcode=dpcode, type_data=current_definition.values
                    )
                )
            ):
                return type_information

    return None
