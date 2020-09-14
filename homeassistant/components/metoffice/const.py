"""Constants for Met Office Integration."""
from datetime import timedelta

DOMAIN = "metoffice"

DEFAULT_NAME = "Met Office"
ATTRIBUTION = "Data provided by the Met Office"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

METOFFICE_DATA = "metoffice_data"
METOFFICE_COORDINATOR = "metoffice_coordinator"
METOFFICE_MONITORED_CONDITIONS = "metoffice_monitored_conditions"
METOFFICE_NAME = "metoffice_name"

MODE_3HOURLY = "3hourly"

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
