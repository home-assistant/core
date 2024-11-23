"""Constants for Met Office Integration."""

from datetime import timedelta

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

DOMAIN = "metoffice"

DEFAULT_NAME = "Met Office"
ATTRIBUTION = "Data provided by the Met Office"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

METOFFICE_COORDINATES = "metoffice_coordinates"
METOFFICE_HOURLY_COORDINATOR = "metoffice_hourly_coordinator"
METOFFICE_DAILY_COORDINATOR = "metoffice_daily_coordinator"
METOFFICE_MONITORED_CONDITIONS = "metoffice_monitored_conditions"
METOFFICE_NAME = "metoffice_name"

# See mapping here: https://github.com/EJEP/datapoint-python/blob/master/src/datapoint/weather_codes.py
HOURLY_CONDITION_CLASSES: dict[str, list[str]] = {
    ATTR_CONDITION_CLEAR_NIGHT: ["Clear night"],
    ATTR_CONDITION_CLOUDY: ["Cloudy", "Overcast"],
    ATTR_CONDITION_FOG: ["Mist", "Fog"],
    ATTR_CONDITION_HAIL: ["Hail shower", "Hail"],
    ATTR_CONDITION_LIGHTNING: ["Thunder"],
    ATTR_CONDITION_LIGHTNING_RAINY: ["Thunder shower"],
    ATTR_CONDITION_PARTLYCLOUDY: ["Partly cloudy"],
    ATTR_CONDITION_POURING: ["Heavy rain shower", "Heavy rain"],
    ATTR_CONDITION_RAINY: ["Light rain shower", "Drizzle", "Light rain"],
    ATTR_CONDITION_SNOWY: [
        "Light snow shower",
        "Light snow",
        "Heavy snow shower",
        "Heavy snow",
    ],
    ATTR_CONDITION_SNOWY_RAINY: ["Sleet shower", "Sleet"],
    ATTR_CONDITION_SUNNY: ["Sunny day"],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}
HOURLY_CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in HOURLY_CONDITION_CLASSES.items()
    for cond_code in cond_codes
}

DAILY_CONDITION_CLASSES: dict[str, list[int]] = {
    ATTR_CONDITION_CLEAR_NIGHT: [0],
    ATTR_CONDITION_CLOUDY: [7, 8],
    ATTR_CONDITION_FOG: [5, 6],
    ATTR_CONDITION_HAIL: [19, 20, 21],
    ATTR_CONDITION_LIGHTNING: [30],
    ATTR_CONDITION_LIGHTNING_RAINY: [28, 29],
    ATTR_CONDITION_PARTLYCLOUDY: [2, 3],
    ATTR_CONDITION_POURING: [13, 14, 15],
    ATTR_CONDITION_RAINY: [9, 10, 11, 12],
    ATTR_CONDITION_SNOWY: [22, 23, 24, 25, 26, 27],
    ATTR_CONDITION_SNOWY_RAINY: [16, 17, 18],
    ATTR_CONDITION_SUNNY: [1],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}
DAILY_CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in DAILY_CONDITION_CLASSES.items()
    for cond_code in cond_codes
}
