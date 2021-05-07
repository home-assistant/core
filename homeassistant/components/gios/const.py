"""Constants for GIOS integration."""
from datetime import timedelta

from homeassistant.components.air_quality import (
    ATTR_CO,
    ATTR_NO2,
    ATTR_OZONE,
    ATTR_PM_2_5,
    ATTR_PM_10,
    ATTR_SO2,
)

ATTRIBUTION = "Data provided by GIOŚ"

ATTR_STATION = "station"
CONF_STATION_ID = "station_id"
DEFAULT_NAME = "GIOŚ"
# Term of service GIOŚ allow downloading data no more than twice an hour.
SCAN_INTERVAL = timedelta(minutes=30)
DOMAIN = "gios"
MANUFACTURER = "Główny Inspektorat Ochrony Środowiska"

API_AQI = "aqi"
API_CO = "co"
API_NO2 = "no2"
API_O3 = "o3"
API_PM10 = "pm10"
API_PM25 = "pm2.5"
API_SO2 = "so2"

API_TIMEOUT = 30

AQI_GOOD = "dobry"
AQI_MODERATE = "umiarkowany"
AQI_POOR = "dostateczny"
AQI_VERY_GOOD = "bardzo dobry"
AQI_VERY_POOR = "zły"

ICONS_MAP = {
    AQI_VERY_GOOD: "mdi:emoticon-excited",
    AQI_GOOD: "mdi:emoticon-happy",
    AQI_MODERATE: "mdi:emoticon-neutral",
    AQI_POOR: "mdi:emoticon-sad",
    AQI_VERY_POOR: "mdi:emoticon-dead",
}

SENSOR_MAP = {
    API_CO: ATTR_CO,
    API_NO2: ATTR_NO2,
    API_O3: ATTR_OZONE,
    API_PM10: ATTR_PM_10,
    API_PM25: ATTR_PM_2_5,
    API_SO2: ATTR_SO2,
}
