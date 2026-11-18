"""Shared utilities for the Daikin Onecta integration."""

from decimal import ROUND_HALF_UP, Decimal
import re


def enum_value_to_state(value: str) -> str:
    """Normalize Daikin's camelCase enum values for Home Assistant states."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def is_read_only_on_off_value(settable: bool, values: list[str] | None) -> bool:
    """Return whether a characteristic is a read-only on/off string value."""
    return not settable and values is not None and set(values) == {"on", "off"}


def round_temperature_to_step(value: float, step: float) -> float:
    """Round a temperature to its nearest step without float noise.

    Halfway values round away from zero, matching the conventional behavior
    expected for user supplied temperature targets.
    """
    value_decimal = Decimal(str(value))
    step_decimal = Decimal(str(step))
    steps = (value_decimal / step_decimal).to_integral_value(rounding=ROUND_HALF_UP)
    return float(steps * step_decimal)
