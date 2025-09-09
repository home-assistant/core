"""Utility methods for the Tuya integration."""

from __future__ import annotations

from tuya_sharing import CustomerDevice

from homeassistant.exceptions import ServiceValidationError

from .const import DOMAIN, DPCode


def get_dpcode(
    device: CustomerDevice, dpcodes: str | DPCode | tuple[DPCode, ...] | None
) -> DPCode | None:
    """Get the first matching DPCode from the device or return None."""
    if dpcodes is None:
        return None

    if isinstance(dpcodes, DPCode):
        dpcodes = (dpcodes,)
    elif isinstance(dpcodes, str):
        dpcodes = (DPCode(dpcodes),)

    for dpcode in dpcodes:
        if (
            dpcode in device.function
            or dpcode in device.status
            or dpcode in device.status_range
        ):
            return dpcode

    return None


def remap_value(
    value: float,
    from_min: float = 0,
    from_max: float = 255,
    to_min: float = 0,
    to_max: float = 255,
    reverse: bool = False,
) -> float:
    """Remap a value from its current range, to a new range."""
    if reverse:
        value = from_max - value + from_min
    return ((value - from_min) / (from_max - from_min)) * (to_max - to_min) + to_min


class ActionDPCodeNotFoundError(ServiceValidationError):
    """Custom exception for action DP code not found errors."""

    def __init__(
        self, device: CustomerDevice, expected: str | DPCode | tuple[DPCode, ...] | None
    ) -> None:
        """Initialize the error with device and expected DP codes."""
        if expected is None:
            expected = ()  # empty tuple for no expected codes
        elif isinstance(expected, str):
            expected = (DPCode(expected),)

        super().__init__(
            translation_domain=DOMAIN,
            translation_key="action_dpcode_not_found",
            translation_placeholders={
                "expected": str(sorted([dp.value for dp in expected])),
                "available": str(sorted(device.function.keys())),
            },
        )
