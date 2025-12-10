"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal, Self, cast, overload

from tuya_sharing import CustomerDevice

from homeassistant.util.json import json_loads, json_loads_object

from .const import LOGGER, DPType
from .util import parse_dptype, remap_value

# Dictionary to track logged warnings to avoid spamming logs
# Keyed by device ID
DEVICE_WARNINGS: dict[str, set[str]] = {}


def _should_log_warning(device_id: str, warning_key: str) -> bool:
    """Check if a warning has already been logged for a device and add it if not.

    Returns: False if the warning was already logged, True if it was added.
    """
    if (device_warnings := DEVICE_WARNINGS.get(device_id)) is None:
        device_warnings = set()
        DEVICE_WARNINGS[device_id] = device_warnings
    if warning_key in device_warnings:
        return False
    DEVICE_WARNINGS[device_id].add(warning_key)
    return True


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
class IntegerTypeData(TypeInformation):
    """Integer Type Data."""

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
        """Load JSON string and return a IntegerTypeData object."""
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
class BitmapTypeInformation(TypeInformation):
    """Bitmap type information."""

    label: list[str]

    @classmethod
    def from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a BitmapTypeInformation object."""
        if not (parsed := cast(dict[str, Any] | None, json_loads_object(type_data))):
            return None
        return cls(
            dpcode=dpcode,
            type_data=type_data,
            label=parsed["label"],
        )


@dataclass(kw_only=True)
class EnumTypeData(TypeInformation):
    """Enum Type Data."""

    range: list[str]

    @classmethod
    def from_json(cls, dpcode: str, type_data: str) -> Self | None:
        """Load JSON string and return a EnumTypeData object."""
        if not (parsed := json_loads_object(type_data)):
            return None
        return cls(
            dpcode=dpcode,
            type_data=type_data,
            **cast(dict[str, list[str]], parsed),
        )


_TYPE_INFORMATION_MAPPINGS: dict[DPType, type[TypeInformation]] = {
    DPType.BITMAP: BitmapTypeInformation,
    DPType.BOOLEAN: TypeInformation,
    DPType.ENUM: EnumTypeData,
    DPType.INTEGER: IntegerTypeData,
    DPType.JSON: TypeInformation,
    DPType.RAW: TypeInformation,
    DPType.STRING: TypeInformation,
}


class DPCodeWrapper:
    """Base DPCode wrapper.

    Used as a common interface for referring to a DPCode, and
    access read conversion routines.
    """

    native_unit: str | None = None
    suggested_unit: str | None = None

    def __init__(self, dpcode: str) -> None:
        """Init DPCodeWrapper."""
        self.dpcode = dpcode

    def _read_device_status_raw(self, device: CustomerDevice) -> Any | None:
        """Read the raw device status for the DPCode.

        Private helper method for `read_device_status`.
        """
        return device.status.get(self.dpcode)

    def read_device_status(self, device: CustomerDevice) -> Any | None:
        """Read the device value for the dpcode.

        The raw device status is converted to a Home Assistant value.
        """
        raise NotImplementedError

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value.

        This is called by `get_update_command` to prepare the value for sending
        back to the device, and should be implemented in concrete classes if needed.
        """
        raise NotImplementedError

    def get_update_command(self, device: CustomerDevice, value: Any) -> dict[str, Any]:
        """Get the update command for the dpcode.

        The Home Assistant value is converted back to a raw device value.
        """
        return {
            "code": self.dpcode,
            "value": self._convert_value_to_raw_value(device, value),
        }


class DPCodeTypeInformationWrapper[T: TypeInformation](DPCodeWrapper):
    """Base DPCode wrapper with Type Information."""

    DPTYPE: DPType
    type_information: T

    def __init__(self, dpcode: str, type_information: T) -> None:
        """Init DPCodeWrapper."""
        super().__init__(dpcode)
        self.type_information = type_information

    @classmethod
    def find_dpcode(
        cls,
        device: CustomerDevice,
        dpcodes: str | tuple[str, ...] | None,
        *,
        prefer_function: bool = False,
    ) -> Self | None:
        """Find and return a DPCodeTypeInformationWrapper for the given DP codes."""
        if type_information := find_dpcode(  # type: ignore[call-overload]
            device, dpcodes, dptype=cls.DPTYPE, prefer_function=prefer_function
        ):
            return cls(
                dpcode=type_information.dpcode, type_information=type_information
            )
        return None


class DPCodeBase64Wrapper(DPCodeTypeInformationWrapper[TypeInformation]):
    """Wrapper to extract information from a RAW/binary value."""

    DPTYPE = DPType.RAW

    def read_bytes(self, device: CustomerDevice) -> bytes | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_device_status_raw(device)) is None or (
            len(decoded := base64.b64decode(raw_value)) == 0
        ):
            return None
        return decoded


class DPCodeBooleanWrapper(DPCodeTypeInformationWrapper[TypeInformation]):
    """Simple wrapper for boolean values.

    Supports True/False only.
    """

    DPTYPE = DPType.BOOLEAN

    def read_device_status(self, device: CustomerDevice) -> bool | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_device_status_raw(device)) in (True, False):
            return raw_value
        return None

    def _convert_value_to_raw_value(
        self, device: CustomerDevice, value: Any
    ) -> Any | None:
        """Convert a Home Assistant value back to a raw device value."""
        if value in (True, False):
            return value
        # Currently only called with boolean values
        # Safety net in case of future changes
        raise ValueError(f"Invalid boolean value `{value}`")


class DPCodeJsonWrapper(DPCodeTypeInformationWrapper[TypeInformation]):
    """Wrapper to extract information from a JSON value."""

    DPTYPE = DPType.JSON

    def read_json(self, device: CustomerDevice) -> Any | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_device_status_raw(device)) is None:
            return None
        return json_loads(raw_value)


class DPCodeEnumWrapper(DPCodeTypeInformationWrapper[EnumTypeData]):
    """Simple wrapper for EnumTypeData values."""

    DPTYPE = DPType.ENUM

    def read_device_status(self, device: CustomerDevice) -> str | None:
        """Read the device value for the dpcode.

        Values outside of the list defined by the Enum type information will
        return None.
        """
        if (raw_value := self._read_device_status_raw(device)) is None:
            return None
        if raw_value not in self.type_information.range:
            if _should_log_warning(
                device.id, f"enum_out_range|{self.dpcode}|{raw_value}"
            ):
                LOGGER.warning(
                    "Found invalid enum value `%s` for datapoint `%s` in product id `%s`,"
                    " expected one of `%s`; please report this defect to Tuya support",
                    raw_value,
                    self.dpcode,
                    device.product_id,
                    self.type_information.range,
                )
            return None
        return raw_value

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value."""
        if value in self.type_information.range:
            return value
        # Guarded by select option validation
        # Safety net in case of future changes
        raise ValueError(
            f"Enum value `{value}` out of range: {self.type_information.range}"
        )


class DPCodeIntegerWrapper(DPCodeTypeInformationWrapper[IntegerTypeData]):
    """Simple wrapper for IntegerTypeData values."""

    DPTYPE = DPType.INTEGER

    def __init__(self, dpcode: str, type_information: IntegerTypeData) -> None:
        """Init DPCodeIntegerWrapper."""
        super().__init__(dpcode, type_information)
        self.native_unit = type_information.unit

    def read_device_status(self, device: CustomerDevice) -> float | None:
        """Read the device value for the dpcode.

        Value will be scaled based on the Integer type information.
        """
        if (raw_value := self._read_device_status_raw(device)) is None:
            return None
        return raw_value / (10**self.type_information.scale)

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value."""
        new_value = round(value * (10**self.type_information.scale))
        if self.type_information.min <= new_value <= self.type_information.max:
            return new_value
        # Guarded by number validation
        # Safety net in case of future changes
        raise ValueError(
            f"Value `{new_value}` (converted from `{value}`) out of range:"
            f" ({self.type_information.min}-{self.type_information.max})"
        )


class DPCodeStringWrapper(DPCodeTypeInformationWrapper[TypeInformation]):
    """Wrapper to extract information from a STRING value."""

    DPTYPE = DPType.STRING

    def read_device_status(self, device: CustomerDevice) -> str | None:
        """Read the device value for the dpcode."""
        return self._read_device_status_raw(device)


class DPCodeBitmapBitWrapper(DPCodeWrapper):
    """Simple wrapper for a specific bit in bitmap values."""

    def __init__(self, dpcode: str, mask: int) -> None:
        """Init DPCodeBitmapWrapper."""
        super().__init__(dpcode)
        self._mask = mask

    def read_device_status(self, device: CustomerDevice) -> bool | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_device_status_raw(device)) is None:
            return None
        return (raw_value & (1 << self._mask)) != 0

    @classmethod
    def find_dpcode(
        cls,
        device: CustomerDevice,
        dpcodes: str | tuple[str, ...],
        *,
        bitmap_key: str,
    ) -> Self | None:
        """Find and return a DPCodeBitmapBitWrapper for the given DP codes."""
        if (
            type_information := find_dpcode(device, dpcodes, dptype=DPType.BITMAP)
        ) and bitmap_key in type_information.label:
            return cls(
                type_information.dpcode, type_information.label.index(bitmap_key)
            )
        return None


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
) -> EnumTypeData | None: ...


@overload
def find_dpcode(
    device: CustomerDevice,
    dpcodes: str | tuple[str, ...] | None,
    *,
    prefer_function: bool = False,
    dptype: Literal[DPType.INTEGER],
) -> IntegerTypeData | None: ...


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
