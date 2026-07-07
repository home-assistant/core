"""Consts for Kaiterra integration."""

from datetime import timedelta

from homeassistant.const import Platform, UnitOfDensity, UnitOfRatio

DOMAIN = "kaiterra"

DISPATCHER_KAITERRA = "kaiterra_update"

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

ATTR_VOC = "volatile_organic_compounds"
ATTR_AQI_LEVEL = "air_quality_index_level"
ATTR_AQI_POLLUTANT = "air_quality_index_pollutant"

AVAILABLE_AQI_STANDARDS = ["us", "cn", "in"]
AVAILABLE_UNITS = [
    "x",
    UnitOfRatio.PERCENTAGE,
    "C",
    "F",
    UnitOfDensity.MILLIGRAMS_PER_CUBIC_METER,
    UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
    UnitOfRatio.PARTS_PER_MILLION,
    UnitOfRatio.PARTS_PER_BILLION,
]
AVAILABLE_DEVICE_TYPES = ["laseregg", "sensedge"]

CONF_AQI_STANDARD = "aqi_standard"
CONF_PREFERRED_UNITS = "preferred_units"

DEFAULT_AQI_STANDARD = "us"
DEFAULT_PREFERRED_UNIT: list[str] = []
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

PLATFORMS = [Platform.AIR_QUALITY, Platform.SENSOR]
