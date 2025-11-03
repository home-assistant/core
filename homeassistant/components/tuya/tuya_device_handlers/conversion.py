"""Base quirk definition."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

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
