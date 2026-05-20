"""Constants for the School Holidays integration."""

from __future__ import annotations

from datetime import timedelta
import logging

LOGGER = logging.getLogger(__package__)

CONF_CALENDAR_NAME = "calendar_name"
CONF_SENSOR_NAME = "sensor_name"

DOMAIN = "school_holiday"
SCAN_INTERVAL = timedelta(hours=24)

# Country and region codes.
COUNTRIES = ["nl"]
REGIONS = {
    "nl": ["midden", "noord", "zuid"],
}

# Country and region names for mapping.
COUNTRY_NAMES = {
    "nl": "The Netherlands",
}

REGION_NAMES = {
    "nl": {
        "midden": "Central",
        "noord": "North",
        "zuid": "South",
    },
}
