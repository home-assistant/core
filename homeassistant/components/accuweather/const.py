"""Constants for AccuWeather integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)

API_METRIC: Final = "Metric"
ATTRIBUTION: Final = "Data provided by AccuWeather"
ATTR_CATEGORY_VALUE = "CategoryValue"
ATTR_DIRECTION: Final = "Direction"
ATTR_ENGLISH: Final = "English"
ATTR_LEVEL: Final = "level"
ATTR_SPEED: Final = "Speed"
ATTR_VALUE: Final = "Value"
DOMAIN: Final = "accuweather"
MANUFACTURER: Final = "AccuWeather, Inc."
MAX_FORECAST_DAYS: Final = 4

CONDITION_CLASSES: Final[dict[str, list[int]]] = {
    ATTR_CONDITION_CLEAR_NIGHT: [33, 34, 37],
    ATTR_CONDITION_CLOUDY: [7, 8, 38],
    ATTR_CONDITION_EXCEPTIONAL: [24, 30, 31],
    ATTR_CONDITION_FOG: [11],
    ATTR_CONDITION_HAIL: [25],
    ATTR_CONDITION_LIGHTNING: [15],
    ATTR_CONDITION_LIGHTNING_RAINY: [16, 17, 41, 42],
    ATTR_CONDITION_PARTLYCLOUDY: [3, 4, 6, 35, 36],
    ATTR_CONDITION_POURING: [18],
    ATTR_CONDITION_RAINY: [12, 13, 14, 26, 39, 40],
    ATTR_CONDITION_SNOWY: [19, 20, 21, 22, 23, 43, 44],
    ATTR_CONDITION_SNOWY_RAINY: [29],
    ATTR_CONDITION_SUNNY: [1, 2, 5],
    ATTR_CONDITION_WINDY: [32],
}
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}
AIR_QUALITY_CATEGORY_MAP = {
    1: "good",
    2: "moderate",
    3: "unhealthy",
    4: "very_unhealthy",
    5: "hazardous",
}
POLLEN_CATEGORY_MAP = {
    1: "low",
    2: "moderate",
    3: "high",
    4: "very_high",
    5: "extreme",
}
UPDATE_INTERVAL_OBSERVATION = timedelta(minutes=40)
UPDATE_INTERVAL_DAILY_FORECAST = timedelta(hours=6)
