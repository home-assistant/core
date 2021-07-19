"""Constants for GIOS integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import ATTR_STATE_CLASS, STATE_CLASS_MEASUREMENT
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

from .model import SensorDescription

ATTRIBUTION: Final = "Data provided by GIOŚ"

CONF_STATION_ID: Final = "station_id"
DEFAULT_NAME: Final = "GIOŚ"
# Term of service GIOŚ allow downloading data no more than twice an hour.
SCAN_INTERVAL: Final = timedelta(minutes=30)
DOMAIN: Final = "gios"
MANUFACTURER: Final = "Główny Inspektorat Ochrony Środowiska"

API_TIMEOUT: Final = 30

ATTR_INDEX: Final = "index"
ATTR_STATION: Final = "station"
ATTR_UNIT: Final = "unit"
ATTR_VALUE: Final = "value"
ATTR_STATION_NAME: Final = "station_name"

ATTR_C6H6: Final = "c6h6"
ATTR_CO: Final = "co"
ATTR_NO2: Final = "no2"
ATTR_O3: Final = "o3"
ATTR_PM10: Final = "pm10"
ATTR_PM25: Final = "pm2.5"
ATTR_SO2: Final = "so2"
ATTR_AQI: Final = "aqi"

SENSOR_TYPES: Final[dict[str, SensorDescription]] = {
    ATTR_AQI: {},
    ATTR_C6H6: {
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_CO: {
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_NO2: {
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_O3: {
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_PM10: {
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_PM25: {
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
    ATTR_SO2: {
        ATTR_UNIT: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_STATE_CLASS: STATE_CLASS_MEASUREMENT,
        ATTR_VALUE: round,
    },
}
