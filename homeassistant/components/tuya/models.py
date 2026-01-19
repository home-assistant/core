"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

import logging
from typing import Any, Self

from tuya_sharing import CustomerDevice

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

    max_value: float
    min_value: float
    value_step: float

    options: list[str]

    def skip_update(
        self,
        device: CustomerDevice,
        updated_status_properties: list[str] | None,
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Determine if the wrapper should skip an update.

        The default is to always skip, unless overridden in subclasses.
        """
        return True

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
        updated_status_properties: list[str] | None,
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Determine if the wrapper should skip an update.

        By default, skip if updated_status_properties is given and
        does not include this dpcode.
        """
        return (
            updated_status_properties is None
            or self.dpcode not in updated_status_properties
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

    def __init__(self, dpcode: str, type_information: IntegerTypeInformation) -> None:
        """Init DPCodeDeltaIntegerWrapper."""
        super().__init__(dpcode, type_information)
        self._accumulated_value: float | None = None
        self._last_dp_timestamp: int | None = None

    @property
    def is_delta_report(self) -> bool:
        """Return True if this sensor uses delta reporting."""
        return self.type_information.report_type == "sum"

    def initialize_accumulated_value(self, device: CustomerDevice) -> None:
        """Initialize accumulated value from current device state.

        Called when the entity is added to Home Assistant.
        """
        if not self.is_delta_report:
            return

        raw_value = super().read_device_status(device)
        if raw_value is not None:
            self._accumulated_value = float(raw_value)
            _LOGGER.debug(
                "Initialized accumulated value from device for %s: %s",
                self.dpcode,
                self._accumulated_value,
            )

    def process_delta_update(
        self, device: CustomerDevice, dp_timestamps: dict | None = None
    ) -> None:
        """Process a delta update by accumulating the value.

        Called during state updates to accumulate incremental values.
        """
        if not self.is_delta_report:
            return

        current_timestamp = dp_timestamps.get(self.dpcode) if dp_timestamps else None

        # Skip duplicate updates with same timestamp
        if (
            current_timestamp is not None
            and current_timestamp == self._last_dp_timestamp
        ):
            _LOGGER.debug(
                "Skipping duplicate update for %s (same timestamp: %s)",
                self.dpcode,
                current_timestamp,
            )
            return

        raw_value = super().read_device_status(device)
        if raw_value is None:
            return

        delta = float(raw_value)

        if self._accumulated_value is None:
            self._accumulated_value = delta
            _LOGGER.debug(
                "Initialized accumulated value for %s: %s",
                self.dpcode,
                self._accumulated_value,
            )
        else:
            self._accumulated_value += delta
            _LOGGER.debug(
                "Delta update for %s: +%s, total: %s",
                self.dpcode,
                delta,
                self._accumulated_value,
            )

        self._last_dp_timestamp = current_timestamp

    def read_device_status(self, device: CustomerDevice) -> float | None:
        """Read device status, returning accumulated value for delta reports."""
        if self.is_delta_report:
            return self._accumulated_value
        return super().read_device_status(device)


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
