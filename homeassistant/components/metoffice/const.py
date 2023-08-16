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

MODE_3HOURLY = "3hourly"
MODE_DAILY = "daily"

CONDITION_CLASSES: dict[str, list[str]] = {
    ATTR_CONDITION_CLEAR_NIGHT: ["0"],
    ATTR_CONDITION_CLOUDY: ["7", "8"],
    ATTR_CONDITION_FOG: ["5", "6"],
    ATTR_CONDITION_HAIL: ["19", "20", "21"],
    ATTR_CONDITION_LIGHTNING: ["30"],
    ATTR_CONDITION_LIGHTNING_RAINY: ["28", "29"],
    ATTR_CONDITION_PARTLYCLOUDY: ["2", "3"],
    ATTR_CONDITION_POURING: ["13", "14", "15"],
    ATTR_CONDITION_RAINY: ["9", "10", "11", "12"],
    ATTR_CONDITION_SNOWY: ["22", "23", "24", "25", "26", "27"],
    ATTR_CONDITION_SNOWY_RAINY: ["16", "17", "18"],
    ATTR_CONDITION_SUNNY: ["1"],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}
<<<<<<< HEAD
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}
=======
>>>>>>> dde6ce6a996 (Add unit tests)

VISIBILITY_CLASSES = {
    "VP": "Very Poor",
    "PO": "Poor",
    "MO": "Moderate",
    "GO": "Good",
    "VG": "Very Good",
    "EX": "Excellent",
}

VISIBILITY_DISTANCE_CLASSES = {
    "VP": "<1",
    "PO": "1-4",
    "MO": "4-10",
    "GO": "10-20",
    "VG": "20-40",
    "EX": ">40",
}
