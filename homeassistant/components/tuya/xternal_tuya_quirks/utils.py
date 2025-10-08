"""Common utility functions for Tuya quirks."""

from typing import Any

from ..models import IntegerTypeData


def scale_value(value: float, step: float, scale: float) -> Any:
    """Official scaling function from Tuya.

    See https://support.tuya.com/en/help/_detail/Kadi66s463e2q
    """
    return step * value / (10**scale)


def scale_value_force_scale_1(dptype: IntegerTypeData, value: float) -> float:
    """Some devices have incorrect scale, force scale=1."""
    return scale_value(value, dptype.step, 1)
