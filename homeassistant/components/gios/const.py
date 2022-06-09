"""Constants for GIOS integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER

from .model import GiosSensorEntityDescription

ATTRIBUTION: Final = "Data provided by GIOŚ"

CONF_STATION_ID: Final = "station_id"
DEFAULT_NAME: Final = "GIOŚ"
# Term of service GIOŚ allow downloading data no more than twice an hour.
SCAN_INTERVAL: Final = timedelta(minutes=30)
DOMAIN: Final = "gios"
MANUFACTURER: Final = "Główny Inspektorat Ochrony Środowiska"

URL = "http://powietrze.gios.gov.pl/pjp/current/station_details/info/{station_id}"

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
        device_class=SensorDeviceClass.AQI,
        value=None,
    ),
    GiosSensorEntityDescription(
        key=ATTR_C6H6,
        name="C6H6",
        icon="mdi:molecule",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_CO,
        name="CO",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_NO2,
        name="NO2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_O3,
        name="O3",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM10,
        name="PM10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_PM25,
        name="PM2.5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    GiosSensorEntityDescription(
        key=ATTR_SO2,
        name="SO2",
        device_class=SensorDeviceClass.SULPHUR_DIOXIDE,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
