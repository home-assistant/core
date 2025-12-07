"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import base64
from typing import Any, Self

from tuya_sharing import CustomerDevice

from homeassistant.util.json import json_loads

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

    _DPTYPE: type[T]
    type_information: T

    def __init__(self, dpcode: str, type_information: T) -> None:
        """Init DPCodeWrapper."""
        super().__init__(dpcode)
        self.type_information = type_information

    def read_device_status(self, device: CustomerDevice) -> Any | None:
        """Read the device value for the dpcode."""
        return self.type_information.process_raw_value(
            self._read_device_status_raw(device), device
        )

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


class DPCodeBase64Wrapper(DPCodeTypeInformationWrapper[RawTypeInformation]):
    """Wrapper to extract information from a RAW/binary value."""

    _DPTYPE = RawTypeInformation

    def read_bytes(self, device: CustomerDevice) -> bytes | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_device_status_raw(device)) is None or (
            len(decoded := base64.b64decode(raw_value)) == 0
        ):
            return None
        return decoded


class DPCodeBooleanWrapper(DPCodeTypeInformationWrapper[BooleanTypeInformation]):
    """Simple wrapper for boolean values.

    Supports True/False only.
    """

    _DPTYPE = BooleanTypeInformation

    def _convert_value_to_raw_value(
        self, device: CustomerDevice, value: Any
    ) -> Any | None:
        """Convert a Home Assistant value back to a raw device value."""
        if value in (True, False):
            return value
        # Currently only called with boolean values
        # Safety net in case of future changes
        raise ValueError(f"Invalid boolean value `{value}`")


class DPCodeJsonWrapper(DPCodeTypeInformationWrapper[JsonTypeInformation]):
    """Wrapper to extract information from a JSON value."""

    _DPTYPE = JsonTypeInformation

    def read_json(self, device: CustomerDevice) -> Any | None:
        """Read the device value for the dpcode."""
        if (raw_value := self._read_device_status_raw(device)) is None:
            return None
        return json_loads(raw_value)


class DPCodeEnumWrapper(DPCodeTypeInformationWrapper[EnumTypeInformation]):
    """Simple wrapper for EnumTypeInformation values."""

    _DPTYPE = EnumTypeInformation

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

    _DPTYPE = IntegerTypeInformation

    def __init__(self, dpcode: str, type_information: IntegerTypeInformation) -> None:
        """Init DPCodeIntegerWrapper."""
        super().__init__(dpcode, type_information)
        self.native_unit = type_information.unit

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


class DPCodeStringWrapper(DPCodeTypeInformationWrapper[StringTypeInformation]):
    """Wrapper to extract information from a STRING value."""

    _DPTYPE = StringTypeInformation


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
            type_information := BitmapTypeInformation.find_dpcode(device, dpcodes)
        ) and bitmap_key in type_information.label:
            return cls(
                type_information.dpcode, type_information.label.index(bitmap_key)
            )
        return None
