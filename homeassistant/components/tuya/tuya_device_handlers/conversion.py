"""Base quirk definition."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

from .utils import scale_value, scale_value_back

if TYPE_CHECKING:
    from tuya_sharing import CustomerDevice


class TuyaIntegerDefinition(Protocol):
    """Definition of an integer type data."""

    dpcode: str
    min: int
    max: int
    scale: float
    step: float
    unit: str | None = None
    type: str | None = None


type TuyaIntegerConversionFunction = Callable[
    [CustomerDevice, TuyaIntegerDefinition, Any], Any
]
"""Start conversion function:

    Args:
        device: The Tuya device instance (CustomerDevice).
        dptype: The DP type data (IntegerTypeData).
        value: The value to convert.
"""


def scale_value_fixed_scale_1(
    _: CustomerDevice, dptype: TuyaIntegerDefinition, value: Any
) -> float:
    """Scale value, overriding scale to be 1."""
    return scale_value(value, dptype.step, 1)


def scale_value_back_fixed_scale_1(
    _: CustomerDevice, dptype: TuyaIntegerDefinition, value: Any
) -> int:
    """Unscale value, overriding scale to be 1."""
    return scale_value_back(value, dptype.step, 1)
