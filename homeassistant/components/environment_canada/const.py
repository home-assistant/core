"""Constants for EC component."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)
from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    UV_INDEX,
)

DOMAIN = "environment_canada"

ATTR_OBSERVATION_TIME = "observation_time"
ATTR_STATION = "station"

CONF_LANGUAGE = "language"
CONF_STATION = "station"
ATTRIBUTION_EN = "Data provided by Environment Canada"
ATTRIBUTION_FR = "Données fournies par xyzzyEnvironnement Canada"

DEFAULT_NAME = "Environment Canada"

# Icon codes from:
# https://dd.weather.gc.ca/citypage_weather/docs/forecast_conditions_icon_code_descriptions_e.csv
EC_ICON_TO_HA_CONDITION_MAP = {
    0: ATTR_CONDITION_SUNNY,
    1: ATTR_CONDITION_SUNNY,
    2: ATTR_CONDITION_PARTLYCLOUDY,
    3: ATTR_CONDITION_PARTLYCLOUDY,
    4: ATTR_CONDITION_PARTLYCLOUDY,
    5: ATTR_CONDITION_PARTLYCLOUDY,
    6: ATTR_CONDITION_RAINY,
    7: ATTR_CONDITION_SNOWY_RAINY,
    8: ATTR_CONDITION_SNOWY,
    9: ATTR_CONDITION_LIGHTNING_RAINY,
    10: ATTR_CONDITION_CLOUDY,
    11: ATTR_CONDITION_CLOUDY,
    12: ATTR_CONDITION_RAINY,
    13: ATTR_CONDITION_POURING,
    14: ATTR_CONDITION_SNOWY_RAINY,
    15: ATTR_CONDITION_SNOWY_RAINY,
    16: ATTR_CONDITION_SNOWY,
    17: ATTR_CONDITION_SNOWY,
    18: ATTR_CONDITION_SNOWY,
    19: ATTR_CONDITION_LIGHTNING_RAINY,
    20: None,
    21: None,
    22: ATTR_CONDITION_PARTLYCLOUDY,
    23: ATTR_CONDITION_FOG,
    24: ATTR_CONDITION_FOG,
    25: None,
    26: None,
    27: ATTR_CONDITION_SNOWY_RAINY,
    28: ATTR_CONDITION_RAINY,
    29: None,
    30: ATTR_CONDITION_CLEAR_NIGHT,
    31: ATTR_CONDITION_CLEAR_NIGHT,
    32: ATTR_CONDITION_PARTLYCLOUDY,
    33: ATTR_CONDITION_PARTLYCLOUDY,
    34: ATTR_CONDITION_PARTLYCLOUDY,
    35: ATTR_CONDITION_PARTLYCLOUDY,
    36: ATTR_CONDITION_RAINY,
    37: ATTR_CONDITION_SNOWY_RAINY,
    38: ATTR_CONDITION_SNOWY,
    39: ATTR_CONDITION_LIGHTNING_RAINY,
    40: ATTR_CONDITION_SNOWY,
    41: None,
    42: None,
    43: ATTR_CONDITION_WINDY,
    44: ATTR_CONDITION_EXCEPTIONAL,
}


@dataclass
class ECSensorEntityDescription(SensorEntityDescription):
    """Class describing ECSensor entities."""

    # key: str | None = None
    # name: str | None = None
    # icon: str | None = None
    # device_class: str | None = None
    unit_convert: str | None = None


SENSOR_TYPES: tuple[ECSensorEntityDescription, ...] = (
    ECSensorEntityDescription(
        key="dewpoint",
        name="Dew Point",
        icon="mdi:thermometer",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="temperature",
        name="Temperature",
        icon="mdi:thermometer",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="low_temp",
        name="Low Temperature",
        icon="mdi:thermometer-chevron-down",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="high_temp",
        name="High Temperature",
        icon="mdi:thermometer-chevron-up",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="wind_chill",
        name="Wind Chill",
        icon="mdi:thermometer-minus",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="humidex",
        name="Humidex",
        icon="mdi:thermometer-plus",
        device_class=DEVICE_CLASS_TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        unit_convert=TEMP_CELSIUS,
    ),
    ECSensorEntityDescription(
        key="humidity",
        name="Humidity",
        icon="mdi:water-percent",
        device_class=DEVICE_CLASS_HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        unit_convert=PERCENTAGE,
    ),
    ECSensorEntityDescription(
        key="wind_speed",
        name="Wind Speed",
        icon="mdi:weather-windy",
        device_class=None,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        unit_convert=SPEED_MILES_PER_HOUR,
    ),
    ECSensorEntityDescription(
        key="wind_gust",
        name="Wind Gust",
        icon="mdi:weather-windy",
        device_class=None,
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        unit_convert=SPEED_MILES_PER_HOUR,
    ),
    ECSensorEntityDescription(
        key="wind_bearing",
        name="Wind Bearing",
        icon="mdi:compass",
        device_class=None,
        native_unit_of_measurement=DEGREE,
        unit_convert=DEGREE,
    ),
    ECSensorEntityDescription(
        key="pressure",
        name="Barometric Pressure",
        icon="mdi:gauge",
        device_class=DEVICE_CLASS_PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        unit_convert=PRESSURE_INHG,
    ),
    ECSensorEntityDescription(
        key="visibility",
        name="Visibility",
        icon="mdi:telescope",
        device_class=None,
        native_unit_of_measurement=LENGTH_KILOMETERS,
        unit_convert=LENGTH_MILES,
    ),
    ECSensorEntityDescription(
        key="pop",
        name="Chance of precipitation",
        icon="mdi:weather-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=PERCENTAGE,
        unit_convert=PERCENTAGE,
    ),
    ECSensorEntityDescription(
        key="precip_yesterday",
        name="Precipitation yesterday",
        icon="mdi:weather-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        unit_convert=LENGTH_INCHES,
    ),
    ECSensorEntityDescription(
        key="uv_index",
        name="UV Index",
        icon="mdi:weather-sunny-alert",
        device_class=None,
        native_unit_of_measurement=UV_INDEX,
        unit_convert=UV_INDEX,
    ),
    ECSensorEntityDescription(
        key="condition",
        name="Current Condition",
        icon="mdi:weather-partly-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="icon_code",
        name="Icon Code",
        icon="mdi:weather-partly-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="tendency",
        name="Tendency",
        icon="mdi:swap-vertical",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="text_summary",
        name="Summary",
        icon="mdi:weather-partly-snowy-rainy",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
    ECSensorEntityDescription(
        key="wind_dir",
        name="Wind Direction",
        icon="mdi:sign-direction",
        device_class=None,
        native_unit_of_measurement=None,
        unit_convert=None,
    ),
)

AQHI_SENSOR = ECSensorEntityDescription(
    key="aqhi",
    name="AQHI",
    icon="mdi:lungs",
    device_class=None,
    native_unit_of_measurement=None,
    unit_convert=None,
)
