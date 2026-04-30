"""Pure helpers for the Indoor Air Quality integration."""

from collections.abc import Mapping
import logging
from typing import Final

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

_LOGGER: Final = logging.getLogger(__name__)


_UGM3_UNITS: Final = frozenset({"µg/m³", "µg/m3", "µg/m^3", "ug/m³", "ug/m3", "ug/m^3"})
_MGM3_UNITS: Final = frozenset({"mg/m³", "mg/m3", "mg/m^3"})


def normalise_unit(unit: str | None) -> str | None:
    """Normalise common ASCII / micro-sign concentration unit aliases.

    Sensors typically report µg/m³ using the micro-sign (U+00B5) while
    Home Assistant's canonical constants use the Greek mu (U+03BC).
    Variants like ``ug/m3`` or ``mg/m^3`` are also normalised so that the
    core unit converters accept the value.
    """
    if unit is None:
        return None
    if unit in _UGM3_UNITS:
        return CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    if unit in _MGM3_UNITS:
        return CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER
    return unit


def has_state(state: str | None) -> bool:
    """Return True if a state has a usable value."""
    return state is not None and state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)


def resolve_state(
    hass: HomeAssistant, entity_id: str
) -> tuple[float, str | None] | None:
    """Resolve an entity's numeric state and unit, or ``None``."""
    entity = hass.states.get(entity_id)
    if entity is None:
        _LOGGER.warning("Entity %s not found", entity_id)
        return None
    if not has_state(entity.state):
        _LOGGER.debug("State of entity %s is unknown", entity_id)
        return None
    try:
        value = float(entity.state)
    except TypeError, ValueError:
        _LOGGER.debug("State of entity %s is not numeric: %r", entity_id, entity.state)
        return None
    return value, entity.attributes.get(ATTR_UNIT_OF_MEASUREMENT)


def convert_value(
    value: float,
    unit: str | None,
    target_units: Mapping[str, float],
    *,
    molar_mass: float | None = None,
    source_type: str = "",
) -> float | None:
    """Convert ``value`` from ``unit`` to the target unit.

    The first key of ``target_units`` is the target unit; remaining keys list
    aliases and like-family conversions with their multiplicative factor.

    If the source ``unit`` is in a different family (ppm/ppb vs. mg/m³ /
    µg/m³) and ``molar_mass`` is provided, a molar-mass-based conversion is
    performed using the standard 24.45 L/mol molar volume at 25 °C / 1 atm.
    """
    if unit is not None and unit in target_units:
        return value * target_units[unit]

    target_unit = next(iter(target_units))

    if molar_mass is None or unit not in {"ppm", "ppb"}:
        _LOGGER.debug(
            "Unit %r is not convertible to %r for %s source",
            unit,
            target_unit,
            source_type,
        )
        return None

    mm = molar_mass
    if "ppb" in (unit, target_unit):
        mm /= 1000
    if target_unit in _UGM3_UNITS:
        mm *= 1000
    return value * (mm / 24.45)


def entity_ids_from_sources(sources: Mapping[str, str | list[str]]) -> list[str]:
    """Flatten configured sources to a single list of entity ids."""
    entity_ids: list[str] = []
    for value in sources.values():
        if isinstance(value, list):
            entity_ids.extend(value)
        elif value:
            entity_ids.append(value)
    return entity_ids
