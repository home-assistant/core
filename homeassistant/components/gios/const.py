"""Constants for GIOS integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

ATTRIBUTION: Final = "Data provided by GIOŚ"

CONF_STATION_ID: Final = "station_id"
# Term of service GIOŚ allow downloading data no more than twice an hour.
SCAN_INTERVAL: Final = timedelta(minutes=30)
DOMAIN: Final = "gios"
MANUFACTURER: Final = "Główny Inspektorat Ochrony Środowiska"

URL = "https://powietrze.gios.gov.pl/pjp/current/station_details/info/{station_id}"

API_TIMEOUT: Final = 30

ATTR_C6H6: Final = "c6h6"
ATTR_CO: Final = "co"
ATTR_NO2: Final = "no2"
ATTR_O3: Final = "o3"
ATTR_PM10: Final = "pm10"
ATTR_PM25: Final = "pm25"
ATTR_SO2: Final = "so2"
ATTR_AQI: Final = "aqi"
