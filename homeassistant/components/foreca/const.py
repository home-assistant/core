"""Constants for the Foreca integration."""

from datetime import timedelta

from pyforeca import Symbol

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
)

DOMAIN = "foreca"
ATTRIBUTION = "Data provided by Foreca"
UPDATE_INTERVAL = timedelta(minutes=30)
HOURLY_PERIODS = 48
DAILY_PERIODS = 10

_CLOUDINESS_CONDITIONS = {
    0: ATTR_CONDITION_SUNNY,
    1: ATTR_CONDITION_SUNNY,
    2: ATTR_CONDITION_PARTLYCLOUDY,
    3: ATTR_CONDITION_PARTLYCLOUDY,
    4: ATTR_CONDITION_CLOUDY,
    5: ATTR_CONDITION_PARTLYCLOUDY,
    6: ATTR_CONDITION_FOG,
}

_PRECIP_SNOW = 2
_PRECIP_SLEET = 1
_RATE_THUNDER = 4
_RATE_CONTINUOUS = 3


def symbol_to_condition(code: str | None) -> str | None:
    """Map a Foreca symbol code (e.g. "d421") to a Home Assistant condition."""
    symbol = Symbol.parse(code or "")
    if symbol is None:
        return None
    if symbol.precip_rate == _RATE_THUNDER:
        if symbol.precip_type == _PRECIP_SNOW:
            return ATTR_CONDITION_SNOWY
        return ATTR_CONDITION_LIGHTNING_RAINY
    if symbol.precip_rate > 0:
        if symbol.precip_type == _PRECIP_SNOW:
            return ATTR_CONDITION_SNOWY
        if symbol.precip_type == _PRECIP_SLEET:
            return ATTR_CONDITION_SNOWY_RAINY
        if symbol.precip_rate == _RATE_CONTINUOUS:
            return ATTR_CONDITION_POURING
        return ATTR_CONDITION_RAINY
    condition = _CLOUDINESS_CONDITIONS.get(symbol.cloudiness)
    if condition == ATTR_CONDITION_SUNNY and not symbol.is_day:
        return ATTR_CONDITION_CLEAR_NIGHT
    return condition
