"""Shared utilities for the Daikin Onecta integration."""

from decimal import ROUND_HALF_UP, Decimal


def round_temperature_to_step(
    value: float,
    step: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    *,
    fallback_minimum: float | None = None,
    fallback_maximum: float | None = None,
) -> float:
    """Round from the native minimum (or zero) and clamp to available bounds.

    Halfway values round away from zero, matching the conventional behavior
    expected for user supplied temperature targets.
    """
    value_decimal = Decimal(str(value))
    step_decimal = (
        Decimal(str(step)) if step is not None and step > 0 else Decimal("0.5")
    )
    lower_bound = minimum if minimum is not None else fallback_minimum
    upper_bound = maximum if maximum is not None else fallback_maximum
    step_origin = Decimal(str(minimum)) if minimum is not None else Decimal(0)
    steps = ((value_decimal - step_origin) / step_decimal).to_integral_value(
        rounding=ROUND_HALF_UP
    )
    rounded = step_origin + steps * step_decimal
    if lower_bound is not None:
        rounded = max(rounded, Decimal(str(lower_bound)))
    if upper_bound is not None:
        rounded = min(rounded, Decimal(str(upper_bound)))
    return float(rounded)
