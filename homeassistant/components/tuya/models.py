"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import base64
from typing import Any, Self

from tuya_sharing import CustomerDevice

from homeassistant.util.json import json_loads

from .const import LOGGER, DPType
from .type_information import (
    EnumTypeInformation,
    IntegerTypeInformation,
    TypeInformation,
    find_dpcode,
)

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

    def _read_device_status_raw(self, device: CustomerDevice) -> Any | None:
        """Read the raw device status for the DPCode.

        Private helper method for `read_device_status`.
        """
        return device.status.get(self.dpcode)

    def _convert_value_to_raw_value(self, device: CustomerDevice, value: Any) -> Any:
        """Convert a Home Assistant value back to a raw device value.

        This is called by `get_update_commands` to prepare the value for sending
        back to the device, and should be implemented in concrete classes if needed.
        """
        raise NotImplementedError

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


class DPCodeEnumWrapper(DPCodeTypeInformationWrapper[EnumTypeInformation]):
    """Simple wrapper for EnumTypeInformation values."""

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


class DPCodeIntegerWrapper(DPCodeTypeInformationWrapper[IntegerTypeInformation]):
    """Simple wrapper for IntegerTypeInformation values."""

    DPTYPE = DPType.INTEGER

    def __init__(self, dpcode: str, type_information: IntegerTypeInformation) -> None:
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
