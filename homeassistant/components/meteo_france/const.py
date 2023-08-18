"""Meteo-France component constants."""
from __future__ import annotations

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

DOMAIN = "meteo_france"
PLATFORMS = [Platform.SENSOR, Platform.WEATHER]
COORDINATOR_FORECAST = "coordinator_forecast"
COORDINATOR_RAIN = "coordinator_rain"
COORDINATOR_ALERT = "coordinator_alert"
UNDO_UPDATE_LISTENER = "undo_update_listener"
ATTRIBUTION = "Data provided by Météo-France"
MODEL = "Météo-France mobile API"
MANUFACTURER = "Météo-France"

CONF_CITY = "city"
FORECAST_MODE_HOURLY = "hourly"
FORECAST_MODE_DAILY = "daily"
FORECAST_MODE_DAILY_HOURLY = "daily & hourly"
FORECAST_MODE = [FORECAST_MODE_HOURLY, FORECAST_MODE_DAILY, FORECAST_MODE_DAILY_HOURLY]

ATTR_NEXT_RAIN_1_HOUR_FORECAST = "1_hour_forecast"
ATTR_NEXT_RAIN_DT_REF = "forecast_time_ref"


CONDITION_CLASSES: dict[str, list[str]] = {
    ATTR_CONDITION_CLEAR_NIGHT: ["Nuit Claire", "Nuit claire"],
    ATTR_CONDITION_CLOUDY: ["Très nuageux", "Couvert"],
    ATTR_CONDITION_FOG: [
        "Brume ou bancs de brouillard",
        "Brume",
        "Brouillard",
        "Brouillard givrant",
        "Bancs de Brouillard",
    ],
    ATTR_CONDITION_HAIL: ["Risque de grêle", "Risque de grèle"],
    ATTR_CONDITION_LIGHTNING: ["Risque d'orages", "Orages"],
    ATTR_CONDITION_LIGHTNING_RAINY: [
        "Pluie orageuses",
        "Pluies orageuses",
        "Averses orageuses",
    ],
    ATTR_CONDITION_PARTLYCLOUDY: [
        "Ciel voilé",
        "Ciel voilé nuit",
        "Éclaircies",
        "Eclaircies",
        "Peu nuageux",
    ],
    ATTR_CONDITION_POURING: ["Pluie forte"],
    ATTR_CONDITION_RAINY: [
        "Bruine / Pluie faible",
        "Bruine",
        "Pluie faible",
        "Pluies éparses / Rares averses",
        "Pluies éparses",
        "Rares averses",
        "Pluie modérée",
        "Pluie / Averses",
        "Averses",
        "Pluie",
    ],
    ATTR_CONDITION_SNOWY: [
        "Neige / Averses de neige",
        "Neige",
        "Averses de neige",
        "Neige forte",
        "Quelques flocons",
    ],
    ATTR_CONDITION_SNOWY_RAINY: ["Pluie et neige", "Pluie verglaçante"],
    ATTR_CONDITION_SUNNY: ["Ensoleillé"],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}
