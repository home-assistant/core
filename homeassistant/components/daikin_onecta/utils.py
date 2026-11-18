"""Shared utilities for the Daikin Onecta integration."""

from decimal import ROUND_HALF_UP, Decimal
import re


def enum_value_to_state(value: str) -> str:
    """Normalize Daikin's camelCase enum values for Home Assistant states."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def is_read_only_on_off_value(settable: bool, values: list[str] | None) -> bool:
    """Return whether a characteristic is a read-only on/off string value."""
    return not settable and values is not None and set(values) == {"on", "off"}


def round_temperature_to_step(
    value: float,
    step: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    *,
    fallback_minimum: float | None = None,
    fallback_maximum: float | None = None,
) -> float:
    """Round and clamp a temperature to its nearest minimum-relative step.

    Halfway values round away from zero, matching the conventional behavior
    expected for user supplied temperature targets.
    """
    value_decimal = Decimal(str(value))
    step_decimal = (
        Decimal(str(step)) if step is not None and step > 0 else Decimal("0.5")
    )
    lower_bound = minimum if minimum is not None else fallback_minimum
    upper_bound = maximum if maximum is not None else fallback_maximum
    minimum_decimal = (
        Decimal(str(lower_bound)) if lower_bound is not None else Decimal(0)
    )
    steps = ((value_decimal - minimum_decimal) / step_decimal).to_integral_value(
        rounding=ROUND_HALF_UP
    )
    rounded = minimum_decimal + steps * step_decimal
    if lower_bound is not None:
        rounded = max(rounded, minimum_decimal)
    if upper_bound is not None:
        rounded = min(rounded, Decimal(str(upper_bound)))
    return float(rounded)
