"""Utility methods for the Tuya integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tuya_sharing import CustomerDevice

from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, DPCode, DPType

if TYPE_CHECKING:
    from .type_information import IntegerTypeInformation

_DPTYPE_MAPPING: dict[str, DPType] = {
    "bitmap": DPType.BITMAP,
    "bool": DPType.BOOLEAN,
    "enum": DPType.ENUM,
    "json": DPType.JSON,
    "raw": DPType.RAW,
    "string": DPType.STRING,
    "value": DPType.INTEGER,
}


def get_dpcode(
    device: CustomerDevice, dpcodes: str | tuple[str, ...] | None
) -> str | None:
    """Get the first matching DPCode from the device or return None."""
    if dpcodes is None:
        return None

    if not isinstance(dpcodes, tuple):
        dpcodes = (dpcodes,)

    for dpcode in dpcodes:
        if (
            dpcode in device.function
            or dpcode in device.status
            or dpcode in device.status_range
        ):
            return dpcode

    return None


def parse_dptype(dptype: str) -> DPType | None:
    """Parse DPType from device DPCode information."""
    try:
        return DPType(dptype)
    except ValueError:
        # Sometimes, we get ill-formed DPTypes from the cloud,
        # this fixes them and maps them to the correct DPType.
        return _DPTYPE_MAPPING.get(dptype)


@dataclass(kw_only=True)
class RemapHelper:
    """Helper class for remapping values."""

    source_min: int
    source_max: int
    target_min: int
    target_max: int

    @classmethod
    def from_type_information(
        cls,
        type_information: IntegerTypeInformation,
        target_min: int,
        target_max: int,
    ) -> RemapHelper:
        """Create RemapHelper from IntegerTypeInformation."""
        return cls(
            source_min=type_information.min,
            source_max=type_information.max,
            target_min=target_min,
            target_max=target_max,
        )

    @classmethod
    def from_function_data(
        cls, function_data: dict[str, Any], target_min: int, target_max: int
    ) -> RemapHelper:
        """Create RemapHelper from function_data."""
        return cls(
            source_min=function_data["min"],
            source_max=function_data["max"],
            target_min=target_min,
            target_max=target_max,
        )

    def remap_value_to(self, value: float, *, reverse: bool = False) -> float:
        """Remap a value from this range to a new range."""
        return self.remap_value(
            value,
            self.source_min,
            self.source_max,
            self.target_min,
            self.target_max,
            reverse=reverse,
        )

    def remap_value_from(self, value: float, *, reverse: bool = False) -> float:
        """Remap a value from its current range to this range."""
        return self.remap_value(
            value,
            self.target_min,
            self.target_max,
            self.source_min,
            self.source_max,
            reverse=reverse,
        )

    @staticmethod
    def remap_value(
        value: float,
        from_min: float,
        from_max: float,
        to_min: float,
        to_max: float,
        *,
        reverse: bool = False,
    ) -> float:
        """Remap a value from its current range, to a new range."""
        if reverse:
            value = from_max - value + from_min
        return ((value - from_min) / (from_max - from_min)) * (to_max - to_min) + to_min


class ActionDPCodeNotFoundError(ServiceValidationError):
    """Custom exception for action DP code not found errors."""

    def __init__(
        self, device: CustomerDevice, expected: str | tuple[str, ...] | None
    ) -> None:
        """Initialize the error with device and expected DP codes."""
        if expected is None:
            expected = ()  # empty tuple for no expected codes
        elif not isinstance(expected, tuple):
            expected = (expected,)

        super().__init__(
            translation_domain=DOMAIN,
            translation_key="action_dpcode_not_found",
            translation_placeholders={
                "expected": str(
                    sorted(
                        [dp.value if isinstance(dp, DPCode) else dp for dp in expected]
                    )
                ),
                "available": str(sorted(device.function.keys())),
            },
        )
