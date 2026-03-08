"""Constants for the Kaiterra integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN = "kaiterra"
MANUFACTURER = "Kaiterra"

CONF_AQI_STANDARD = "aqi_standard"

DEFAULT_AQI_STANDARD = "us"
UPDATE_INTERVAL = timedelta(minutes=1)
PLATFORMS = [Platform.SENSOR]
AVAILABLE_AQI_STANDARDS = ["us", "cn", "in"]
DEFAULT_MODEL = "Air quality monitor"

AQI_SCALE = {
    "cn": [0, 50, 100, 150, 200, 300, 400, 500],
    "in": [0, 50, 100, 200, 300, 400, 500],
    "us": [0, 50, 100, 150, 200, 300, 500],
}
AQI_LEVEL = {
    "cn": [
        "Good",
        "Satisfactory",
        "Moderate",
        "Unhealthy for sensitive groups",
        "Unhealthy",
        "Very unhealthy",
        "Hazardous",
    ],
    "in": [
        "Good",
        "Satisfactory",
        "Moderately polluted",
        "Poor",
        "Very poor",
        "Severe",
    ],
    "us": [
        "Good",
        "Moderate",
        "Unhealthy for sensitive groups",
        "Unhealthy",
        "Very unhealthy",
        "Hazardous",
    ],
}

ATTR_AQI_LEVEL = "air_quality_index_level"
ATTR_AQI_POLLUTANT = "air_quality_index_pollutant"
