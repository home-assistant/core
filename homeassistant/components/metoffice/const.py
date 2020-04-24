"""String constants for Met Office weather service integration."""

ATTR_ATTRIBUTION = "attribution"
ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"
ATTR_SITE_ID = "site_id"
ATTR_SITE_NAME = "site_name"

ATTRIBUTION = "Data provided by the Met Office"

CONDITION_CLASSES = {
    "cloudy": ["7", "8"],
    "fog": ["5", "6"],
    "hail": ["19", "20", "21"],
    "lightning": ["30"],
    "lightning-rainy": ["28", "29"],
    "partlycloudy": ["2", "3"],
    "pouring": ["13", "14", "15"],
    "rainy": ["9", "10", "11", "12"],
    "snowy": ["22", "23", "24", "25", "26", "27"],
    "snowy-rainy": ["16", "17", "18"],
    "sunny": ["0", "1"],
    "windy": [],
    "windy-variant": [],
    "exceptional": [],
}

DEFAULT_NAME = "Met Office"

MODE_3HOURLY = "3hourly"
MODE_DAILY = "daily"

VISIBILITY_CLASSES = {
    "VP": "<1",
    "PO": "1-4",
    "MO": "4-10",
    "GO": "10-20",
    "VG": "20-40",
    "EX": ">40",
}
