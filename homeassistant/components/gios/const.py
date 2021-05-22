"""Constants for GIOS integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.components.air_quality import (
    ATTR_CO,
    ATTR_NO2,
    ATTR_OZONE,
    ATTR_PM_2_5,
    ATTR_PM_10,
    ATTR_SO2,
)

ATTRIBUTION: Final = "Data provided by GIOŚ"

ATTR_STATION: Final = "station"
CONF_STATION_ID: Final = "station_id"
DEFAULT_NAME: Final = "GIOŚ"
# Term of service GIOŚ allow downloading data no more than twice an hour.
SCAN_INTERVAL: Final = timedelta(minutes=30)
DOMAIN: Final = "gios"
MANUFACTURER: Final = "Główny Inspektorat Ochrony Środowiska"

API_AQI: Final = "aqi"
API_CO: Final = "co"
API_NO2: Final = "no2"
API_O3: Final = "o3"
API_PM10: Final = "pm10"
API_PM25: Final = "pm2.5"
API_SO2: Final = "so2"

API_TIMEOUT: Final = 30

AQI_GOOD: Final = "dobry"
AQI_MODERATE: Final = "umiarkowany"
AQI_POOR: Final = "dostateczny"
AQI_VERY_GOOD: Final = "bardzo dobry"
AQI_VERY_POOR: Final = "zły"

ICONS_MAP: Final[dict[str, str]] = {
    AQI_VERY_GOOD: "mdi:emoticon-excited",
    AQI_GOOD: "mdi:emoticon-happy",
    AQI_MODERATE: "mdi:emoticon-neutral",
    AQI_POOR: "mdi:emoticon-sad",
    AQI_VERY_POOR: "mdi:emoticon-dead",
}

SENSOR_MAP: Final[dict[str, str]] = {
    API_CO: ATTR_CO,
    API_NO2: ATTR_NO2,
    API_O3: ATTR_OZONE,
    API_PM10: ATTR_PM_10,
    API_PM25: ATTR_PM_2_5,
    API_SO2: ATTR_SO2,
}
