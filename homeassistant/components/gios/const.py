"""Constants for GIOS integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

from .model import GiosSensorEntityDescription

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

ATTR_C6H6: Final = "c6h6"
ATTR_CO: Final = "co"
ATTR_NO2: Final = "no2"
ATTR_O3: Final = "o3"
ATTR_PM10: Final = "pm10"
ATTR_PM25: Final = "pm25"
ATTR_SO2: Final = "so2"
ATTR_AQI: Final = "aqi"

SENSOR_TYPES: Final[tuple[GiosSensorEntityDescription, ...]] = (
    GiosSensorEntityDescription(
        key=ATTR_AQI,
        name="AQI",
        value=None,
    ),
    GiosSensorEntityDescription(
        key=ATTR_C6H6,
        name="C6H6",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_CO,
        name="CO",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_NO2,
        name="NO2",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_O3,
        name="O3",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM10,
        name="PM10",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM25,
        name="PM2.5",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_SO2,
        name="SO2",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)
