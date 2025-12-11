"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import base64
import json
from typing import Any, Self

from tuya_sharing import CustomerDevice

from .const import LOGGER
from .type_information import (
    BitmapTypeInformation,
    BooleanTypeInformation,
    EnumTypeInformation,
    IntegerTypeInformation,
    JsonTypeInformation,
    RawTypeInformation,
    StringTypeInformation,
    TypeInformation,
)

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


class DeviceWrapper:
    """Base device wrapper."""

    def read_device_status(self, device: CustomerDevice) -> Any | None:
        """Read device status and convert to a Home Assistant value."""
        raise NotImplementedError

    def get_update_commands(
        self, device: CustomerDevice, value: Any
    ) -> list[dict[str, Any]]:
        """Generate update commands for a Home Assistant action."""
        raise NotImplementedError


class DPCodeWrapper(DeviceWrapper):
    """Base device wrapper for a single DPCode.

    Used as a common interface for referring to a DPCode, and
    access read conversion routines.
    """

    native_unit: str | None = None
    suggested_unit: str | None = None

    def __init__(self, dpcode: str) -> None:
        """Init DPCodeWrapper."""
        self.dpcode = dpcode

    def read_device_status(self, device: CustomerDevice) -> Any:
        """Read and process raw value against this type information.

        Base implementation does no validation, subclasses may override to provide
        specific validation.
        """
        return device.status.get(self.dpcode)

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert display value back to a raw device value.

        Base implementation does no validation, subclasses may override to provide
        specific validation.
        """
        return value

    def get_update_commands(
        self, device: CustomerDevice, value: Any
    ) -> list[dict[str, Any]]:
        """Get the update commands for the dpcode.

        The Home Assistant value is converted back to a raw device value.
        """
        return [
            {
                "code": self.dpcode,
                "value": self._convert_value_to_raw_value(device, value),
            }
        ]


class DPCodeTypeInformationWrapper[T: TypeInformation](DPCodeWrapper):
    """Base DPCode wrapper with Type Information."""

    _DPTYPE: type[T]
    type_information: T

    def __init__(self, dpcode: str, type_information: T) -> None:
        """Init DPCodeWrapper."""
        super().__init__(dpcode)
        self.type_information = type_information

    def read_device_status(self, device: CustomerDevice) -> Any | None:
        """Read the device value for the dpcode."""
        return device.status.get(self.dpcode)

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value."""
        return value

    @classmethod
    def find_dpcode(
        cls,
        device: CustomerDevice,
        dpcodes: str | tuple[str, ...] | None,
        *,
        prefer_function: bool = False,
    ) -> Self | None:
        """Find and return a DPCodeTypeInformationWrapper for the given DP codes."""
        if type_information := cls._DPTYPE.find_dpcode(
            device, dpcodes, prefer_function=prefer_function
        ):
            return cls(
                dpcode=type_information.dpcode, type_information=type_information
            )
        return None


class DPCodeBooleanWrapper(DPCodeTypeInformationWrapper[BooleanTypeInformation]):
    """Simple wrapper for BooleanTypeInformation values."""

    _DPTYPE = BooleanTypeInformation

    def read_device_status(self, device: CustomerDevice) -> bool | None:
        """Read and process raw value against this type information."""
        if (raw_value := device.status.get(self.dpcode)) is None:
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

    def _convert_value_to_raw_value(
        self, device: CustomerDevice, value: bool
    ) -> Any | None:
        """Convert a Home Assistant value back to a raw device value."""
        if value in (True, False):
            return value
        # Currently only called with boolean values
        # Safety net in case of future changes
        raise ValueError(f"Invalid boolean value `{value}`")


class DPCodeEnumWrapper(DPCodeTypeInformationWrapper[EnumTypeInformation]):
    """Simple wrapper for EnumTypeInformation values."""

    _DPTYPE = EnumTypeInformation

    def read_device_status(self, device: CustomerDevice) -> str | None:
        """Read and process raw value against this type information."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        # Validate input against defined range
        if raw_value not in self.type_information.range:
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
                    self.type_information.range,
                )
            return None
        return raw_value

    def _convert_value_to_raw_value(
        self, device: CustomerDevice, value: str
    ) -> Any | None:
        """Convert a Home Assistant value back to a raw device value."""
        if value in self.type_information.range:
            return value
        # Guarded by select option validation
        # Safety net in case of future changes
        raise ValueError(
            f"Enum value `{value}` out of range: {self.type_information.range}"
        )


class DPCodeIntegerWrapper(DPCodeTypeInformationWrapper[IntegerTypeInformation]):
    """Simple wrapper for IntegerTypeInformation values."""

    _DPTYPE = IntegerTypeInformation

    def __init__(self, dpcode: str, type_information: IntegerTypeInformation) -> None:
        """Init DPCodeIntegerWrapper."""
        super().__init__(dpcode, type_information)
        self.native_unit = type_information.unit
        self.min = self.type_information.scale_value(type_information.min)
        self.max = self.type_information.scale_value(type_information.max)
        self.step = self.type_information.scale_value(type_information.step)

    def read_device_status(self, device: CustomerDevice) -> float | None:
        """Read and process raw value against this type information."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        # Validate input against defined range
        if not isinstance(raw_value, int) or not (
            self.type_information.min <= raw_value <= self.type_information.max
        ):
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
                    self.type_information.min,
                    self.type_information.max,
                )

            return None
        return self.type_information.scale_value(raw_value)

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: float) -> int:
        """Convert a Home Assistant value back to a raw device value."""
        new_value = self.type_information.scale_value_back(value)
        if self.type_information.min <= new_value <= self.type_information.max:
            return new_value
        # Guarded by number validation
        # Safety net in case of future changes
        raise ValueError(
            f"Value `{new_value}` (converted from `{value}`) out of range:"
            f" ({self.type_information.min}-{self.type_information.max})"
        )


class DPCodeJsonWrapper(DPCodeTypeInformationWrapper[JsonTypeInformation]):
    """Simple wrapper for JsonTypeInformation values."""

    _DPTYPE = JsonTypeInformation

    def read_device_status(self, device: CustomerDevice) -> dict[str, Any] | None:
        """Read and process raw value against this type information."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        return json.loads(raw_value)


class DPCodeRawWrapper(DPCodeTypeInformationWrapper[RawTypeInformation]):
    """Simple wrapper for RawTypeInformation values."""

    _DPTYPE = RawTypeInformation

    def read_device_status(self, device: CustomerDevice) -> bytes | None:
        """Read and process raw value against this type information."""
        if (raw_value := device.status.get(self.dpcode)) is None:
            return None
        return base64.b64decode(raw_value)


class DPCodeStringWrapper(DPCodeTypeInformationWrapper[StringTypeInformation]):
    """Simple wrapper for StringTypeInformation values."""

    _DPTYPE = StringTypeInformation


class DPCodeBitmapBitWrapper(DPCodeWrapper):
    """Simple wrapper for a specific bit in bitmap values."""

    def __init__(self, dpcode: str, mask: int) -> None:
        """Init DPCodeBitmapWrapper."""
        super().__init__(dpcode)
        self._mask = mask

    def read_device_status(self, device: CustomerDevice) -> bool | None:
        """Read the device value for the dpcode."""
        if (raw_value := device.status.get(self.dpcode)) is None:
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
            type_information := BitmapTypeInformation.find_dpcode(device, dpcodes)
        ) and bitmap_key in type_information.label:
            return cls(
                type_information.dpcode, type_information.label.index(bitmap_key)
            )
        return None
