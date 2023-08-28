"""Meteoclimatic component constants."""
from __future__ import annotations

from datetime import timedelta

from meteoclimatic import Condition

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
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.const import Platform

DOMAIN = "meteoclimatic"
PLATFORMS = [Platform.SENSOR, Platform.WEATHER]
ATTRIBUTION = "Data provided by Meteoclimatic"
MODEL = "Meteoclimatic RSS feed"
MANUFACTURER = "Meteoclimatic"

SCAN_INTERVAL = timedelta(minutes=10)

CONF_STATION_CODE = "station_code"

DEFAULT_WEATHER_CARD = True


CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT: [Condition.moon, Condition.hazemoon],
    ATTR_CONDITION_CLOUDY: [Condition.mooncloud],
    ATTR_CONDITION_EXCEPTIONAL: [],
    ATTR_CONDITION_FOG: [Condition.fog, Condition.mist],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING: [Condition.storm],
    ATTR_CONDITION_LIGHTNING_RAINY: [],
    ATTR_CONDITION_PARTLYCLOUDY: [Condition.suncloud, Condition.hazesun],
    ATTR_CONDITION_POURING: [],
    ATTR_CONDITION_RAINY: [Condition.rain],
    ATTR_CONDITION_SNOWY: [],
    ATTR_CONDITION_SNOWY_RAINY: [],
    ATTR_CONDITION_SUNNY: [Condition.sun],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
}
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}
