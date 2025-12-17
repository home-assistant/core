"""Type information classes for the Tuya integration."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, ClassVar, Self, cast

from tuya_sharing import CustomerDevice

from homeassistant.util.json import json_loads_object

from .const import LOGGER, DPType
from .util import parse_dptype

# Dictionary to track logged warnings to avoid spamming logs
# Keyed by device ID
DEVICE_WARNINGS: dict[str, set[str]] = {}


def _should_log_warning(device_id: str, warning_key: str) -> bool:
    """Check if a warning has already been logged for a device and add it if not.

    Returns: True if the warning should be logged, False if it was already logged.
    """
    if (device_warnings := DEVICE_WARNINGS.get(device_id)) is None:
        device_warnings = set()
        DEVICE_WARNINGS[device_id] = device_warnings
    if warning_key in device_warnings:
        return False
    DEVICE_WARNINGS[device_id].add(warning_key)
    return True


@dataclass(kw_only=True)
class TypeInformation[T]:
    """Type information.

    As provided by the SDK, from `device.function` / `device.status_range`.
    """

    _DPTYPE: ClassVar[DPType]
    dpcode: str
    type_data: str

    def process_raw_value(
        self, raw_value: Any | None, device: CustomerDevice
    ) -> T | None:
        """Read and process raw value against this type information.

        Base implementation does no validation, subclasses may override to provide
        specific validation.
        """
        return raw_value

    @classmethod
    def _from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a TypeInformation object."""
        return cls(dpcode=dpcode, type_data=type_data)

    @classmethod
    def find_dpcode(
        cls,
        device: CustomerDevice,
        dpcodes: str | tuple[str, ...] | None,
        *,
        prefer_function: bool = False,
    ) -> Self | None:
        """Find type information for a matching DP code available for this device."""
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
                    and parse_dptype(current_definition.type) is cls._DPTYPE
                    and (
                        type_information := cls._from_json(
                            dpcode=dpcode, type_data=current_definition.values
                        )
                    )
                ):
                    return type_information

        return None


@dataclass(kw_only=True)
class BitmapTypeInformation(TypeInformation[int]):
    """Bitmap type information."""

    _DPTYPE = DPType.BITMAP

    label: list[str]

    @classmethod
    def _from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a BitmapTypeInformation object."""
        if not (parsed := cast(dict[str, Any] | None, json_loads_object(type_data))):
            return None
        return cls(
            dpcode=dpcode,
            type_data=type_data,
            label=parsed["label"],
        )


@dataclass(kw_only=True)
class BooleanTypeInformation(TypeInformation[bool]):
    """Boolean type information."""

    _DPTYPE = DPType.BOOLEAN

    def process_raw_value(
        self, raw_value: Any | None, device: CustomerDevice
    ) -> bool | None:
        """Read and process raw value against this type information."""
        if raw_value is None:
            return None
        # Validate input against defined range
        if raw_value not in (True, False):
            if _should_log_warning(
                device.id, f"boolean_out_range|{self.dpcode}|{raw_value}"
            ):
                LOGGER.warning(
                    "Found invalid boolean value `%s` for datapoint `%s` in product "
                    "id `%s`, expected one of `%s`; please report this defect to "
                    "Tuya support",
                    raw_value,
                    self.dpcode,
                    device.product_id,
                    (True, False),
                )
            return None
        return raw_value


@dataclass(kw_only=True)
class EnumTypeInformation(TypeInformation[str]):
    """Enum type information."""

    _DPTYPE = DPType.ENUM

    range: list[str]

    def process_raw_value(
        self, raw_value: Any | None, device: CustomerDevice
    ) -> str | None:
        """Read and process raw value against this type information."""
        if raw_value is None:
            return None
        # Validate input against defined range
        if raw_value not in self.range:
            if _should_log_warning(
                device.id, f"enum_out_range|{self.dpcode}|{raw_value}"
            ):
                LOGGER.warning(
                    "Found invalid enum value `%s` for datapoint `%s` in product "
                    "id `%s`, expected one of `%s`; please report this defect to "
                    "Tuya support",
                    raw_value,
                    self.dpcode,
                    device.product_id,
                    self.range,
                )
            return None
        return raw_value

    @classmethod
    def _from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return an EnumTypeInformation object."""
        if not (parsed := json_loads_object(type_data)):
            return None
        return cls(
            dpcode=dpcode,
            type_data=type_data,
            **cast(dict[str, list[str]], parsed),
        )


@dataclass(kw_only=True)
class IntegerTypeInformation(TypeInformation[float]):
    """Integer type information."""

    _DPTYPE = DPType.INTEGER

    min: int
    max: int
    scale: int
    step: int
    unit: str | None = None

    def scale_value(self, value: int) -> float:
        """Scale a value."""
        return value / (10**self.scale)

    def scale_value_back(self, value: float) -> int:
        """Return raw value for scaled."""
        return round(value * (10**self.scale))

    def process_raw_value(
        self, raw_value: Any | None, device: CustomerDevice
    ) -> float | None:
        """Read and process raw value against this type information."""
        if raw_value is None:
            return None
        # Validate input against defined range
        if not isinstance(raw_value, int) or not (self.min <= raw_value <= self.max):
            if _should_log_warning(
                device.id, f"integer_out_range|{self.dpcode}|{raw_value}"
            ):
                LOGGER.warning(
                    "Found invalid integer value `%s` for datapoint `%s` in product "
                    "id `%s`, expected integer value between %s and %s; please report "
                    "this defect to Tuya support",
                    raw_value,
                    self.dpcode,
                    device.product_id,
                    self.min,
                    self.max,
                )

            return None
        return raw_value / (10**self.scale)

    @classmethod
    def _from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return an IntegerTypeInformation object."""
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


@dataclass(kw_only=True)
class JsonTypeInformation(TypeInformation[dict[str, Any]]):
    """Json type information."""

    _DPTYPE = DPType.JSON

    def process_raw_value(
        self, raw_value: Any | None, device: CustomerDevice
    ) -> dict[str, Any] | None:
        """Read and process raw value against this type information."""
        if raw_value is None:
            return None
        return json_loads_object(raw_value)


@dataclass(kw_only=True)
class RawTypeInformation(TypeInformation[bytes]):
    """Raw type information."""

    _DPTYPE = DPType.RAW

    def process_raw_value(
        self, raw_value: Any | None, device: CustomerDevice
    ) -> bytes | None:
        """Read and process raw value against this type information."""
        if raw_value is None:
            return None
        return base64.b64decode(raw_value)


@dataclass(kw_only=True)
class StringTypeInformation(TypeInformation[str]):
    """String type information."""

    _DPTYPE = DPType.STRING
