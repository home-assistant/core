"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import logging
from typing import Any, Self

from tuya_sharing import CustomerDevice

from homeassistant.components.sensor import SensorStateClass

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

_LOGGER = logging.getLogger(__name__)


class DeviceWrapper[T]:
    """Base device wrapper."""

    native_unit: str | None = None
    suggested_unit: str | None = None
    state_class: SensorStateClass | None = None

    max_value: float
    min_value: float
    value_step: float

    options: list[str]

    def initialize(self, device: CustomerDevice) -> None:
        """Initialize the wrapper with device data.

        Called when the entity is added to Home Assistant.
        Override in subclasses to perform initialization logic.
        """

    def skip_update(
        self,
        device: CustomerDevice,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Determine if the wrapper should skip an update.

        The default is to always skip if updated properties is given,
        unless overridden in subclasses.
        """
        # If updated_status_properties is None, we should not skip,
        # as we don't have information on what was updated
        # This happens for example on online/offline updates, where
        # we still want to update the entity state
        return updated_status_properties is not None

    def read_device_status(self, device: CustomerDevice) -> T | None:
        """Read device status and convert to a Home Assistant value."""
        raise NotImplementedError

    def get_update_commands(
        self, device: CustomerDevice, value: T
    ) -> list[dict[str, Any]]:
        """Generate update commands for a Home Assistant action."""
        raise NotImplementedError


class DPCodeWrapper(DeviceWrapper):
    """Base device wrapper for a single DPCode.

    Used as a common interface for referring to a DPCode, and
    access read conversion routines.
    """

    def __init__(self, dpcode: str) -> None:
        """Init DPCodeWrapper."""
        self.dpcode = dpcode

    def skip_update(
        self,
        device: CustomerDevice,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Determine if the wrapper should skip an update.

        By default, skip if updated_status_properties is given and
        does not include this dpcode.
        """
        # If updated_status_properties is None, we should not skip,
        # as we don't have information on what was updated
        # This happens for example on online/offline updates, where
        # we still want to update the entity state
        return (
            updated_status_properties is not None
            and self.dpcode not in updated_status_properties
        )

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
            device.status.get(self.dpcode), device
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


class DPCodeEnumWrapper(DPCodeTypeInformationWrapper[EnumTypeInformation]):
    """Simple wrapper for EnumTypeInformation values."""

    _DPTYPE = EnumTypeInformation

    def __init__(self, dpcode: str, type_information: EnumTypeInformation) -> None:
        """Init DPCodeEnumWrapper."""
        super().__init__(dpcode, type_information)
        self.options = type_information.range

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
        self.min_value = self.type_information.scale_value(type_information.min)
        self.max_value = self.type_information.scale_value(type_information.max)
        self.value_step = self.type_information.scale_value(type_information.step)

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


class DPCodeDeltaIntegerWrapper(DPCodeIntegerWrapper):
    """Wrapper for integer values with delta report accumulation.

    This wrapper handles sensors that report incremental (delta) values
    instead of cumulative totals. It accumulates the delta values locally
    to provide a running total.
    """

    _accumulated_value: float = 0
    _last_dp_timestamp: int | None = None

    def __init__(self, dpcode: str, type_information: IntegerTypeInformation) -> None:
        """Init DPCodeDeltaIntegerWrapper."""
        super().__init__(dpcode, type_information)
        # Delta reports use TOTAL_INCREASING state class
        self.state_class = SensorStateClass.TOTAL_INCREASING

    def skip_update(
        self,
        device: CustomerDevice,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Override skip_update to process delta updates.

        Processes delta accumulation before determining if update should be skipped.
        """
        if (
            super().skip_update(device, updated_status_properties, dp_timestamps)
            or dp_timestamps is None
            or (current_timestamp := dp_timestamps.get(self.dpcode)) is None
            or current_timestamp == self._last_dp_timestamp
            or (raw_value := super().read_device_status(device)) is None
        ):
            return True

        delta = float(raw_value)
        self._accumulated_value += delta
        _LOGGER.debug(
            "Delta update for %s: +%s, total: %s",
            self.dpcode,
            delta,
            self._accumulated_value,
        )

        self._last_dp_timestamp = current_timestamp
        return False

    def read_device_status(self, device: CustomerDevice) -> float | None:
        """Read device status, returning accumulated value for delta reports."""
        return self._accumulated_value


class DPCodeRawWrapper(DPCodeTypeInformationWrapper[RawTypeInformation]):
    """Wrapper to extract information from a RAW/binary value."""

    _DPTYPE = RawTypeInformation


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
