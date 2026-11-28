"""Shared utilities for the Daikin Onecta integration."""

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
import re
from typing import Literal

from daikin_onecta.models import FanDirectionMode, FanSpeedMode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity import Entity


def account_identifier(entry: ConfigEntry) -> str:
    """Return the stable account identifier used for registry entries."""
    return entry.unique_id or entry.entry_id


def account_device_identifier(account_id: str) -> str:
    """Return the registry identifier for an account service device."""
    return f"account_{account_id}"


def management_point_unique_id(gateway_id: str, embedded_id: str, *suffix: str) -> str:
    """Return a stable identifier for a management point or its entity."""
    return "_".join((gateway_id, embedded_id, *suffix))


def temperature_unit_or_celsius(unit: str | None) -> UnitOfTemperature:
    """Return Daikin's temperature unit, defaulting invalid or missing values to Celsius."""
    try:
        return (
            UnitOfTemperature(unit) if unit is not None else UnitOfTemperature.CELSIUS
        )
    except ValueError:
        return UnitOfTemperature.CELSIUS


def fixed_positions(mode: FanDirectionMode | FanSpeedMode) -> range | None:
    """Return valid fixed positions from Daikin range metadata."""
    minimum = mode.min_value
    maximum = mode.max_value
    step = mode.step_value
    if minimum is None or maximum is None or step is None or step <= 0:
        return None
    return range(minimum, maximum + 1, step)


def enum_value_to_state(value: str) -> str:
    """Normalize Daikin's camelCase enum values for Home Assistant states."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def is_on_off_value(values: list[str] | None) -> bool:
    """Return whether a characteristic supports exactly on/off values."""
    return values is not None and set(values) == {"on", "off"}


def set_optional_temperature_bound(
    entity: Entity, bound: Literal["min", "max"], value: float | None
) -> None:
    """Set a reported temperature bound or restore Home Assistant's default."""
    attribute = f"_attr_{bound}_temp"
    if value is None:
        if hasattr(entity, attribute):
            delattr(entity, attribute)
    else:
        setattr(entity, attribute, value)


def round_temperature_to_step(
    value: float,
    step: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    *,
    default_step: float = 0.5,
    fallback_minimum: float | None = None,
    fallback_maximum: float | None = None,
) -> int | float:
    """Round from the native minimum (or zero) and clamp to available bounds.

    Halfway values round away from zero, matching the conventional behavior
    expected for user supplied temperature targets.
    """
    value_decimal = Decimal(str(value))
    step_decimal = Decimal(str(step if step is not None and step > 0 else default_step))
    lower_bound = minimum if minimum is not None else fallback_minimum
    upper_bound = maximum if maximum is not None else fallback_maximum
    step_origin = Decimal(str(minimum)) if minimum is not None else Decimal(0)
    step_count = (value_decimal - step_origin) / step_decimal
    lower_steps = step_count.to_integral_value(rounding=ROUND_FLOOR)
    fraction = step_count - lower_steps
    if fraction == Decimal("0.5"):
        lower_value = step_origin + lower_steps * step_decimal
        upper_value = lower_value + step_decimal
        rounded = lower_value if abs(lower_value) > abs(upper_value) else upper_value
    else:
        steps = step_count.to_integral_value(rounding=ROUND_HALF_UP)
        rounded = step_origin + steps * step_decimal
    rounded_steps = (rounded - step_origin) / step_decimal
    if lower_bound is not None:
        minimum_steps = (
            (Decimal(str(lower_bound)) - step_origin) / step_decimal
        ).to_integral_value(rounding=ROUND_CEILING)
        rounded_steps = max(rounded_steps, minimum_steps)
    if upper_bound is not None:
        maximum_steps = (
            (Decimal(str(upper_bound)) - step_origin) / step_decimal
        ).to_integral_value(rounding=ROUND_FLOOR)
        rounded_steps = min(rounded_steps, maximum_steps)
    rounded = step_origin + rounded_steps * step_decimal
    if (
        step_decimal == step_decimal.to_integral_value()
        and rounded == rounded.to_integral_value()
    ):
        return int(rounded)
    return float(rounded)
