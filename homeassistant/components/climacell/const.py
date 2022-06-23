"""Constants for the ClimaCell integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum

from pyclimacell.const import DAILY, HOURLY, NOWCAST, V3PollenIndex

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
)

CONF_TIMESTEP = "timestep"
FORECAST_TYPES = [DAILY, HOURLY, NOWCAST]

DEFAULT_NAME = "ClimaCell"
DEFAULT_TIMESTEP = 15
DEFAULT_FORECAST_TYPE = DAILY
DOMAIN = "climacell"
ATTRIBUTION = "Powered by ClimaCell"

MAX_REQUESTS_PER_DAY = 100

CLEAR_CONDITIONS = {"night": ATTR_CONDITION_CLEAR_NIGHT, "day": ATTR_CONDITION_SUNNY}

MAX_FORECASTS = {
    DAILY: 14,
    HOURLY: 24,
    NOWCAST: 30,
}

# Additional attributes
ATTR_WIND_GUST = "wind_gust"
ATTR_CLOUD_COVER = "cloud_cover"
ATTR_PRECIPITATION_TYPE = "precipitation_type"


@dataclass
class ClimaCellSensorEntityDescription(SensorEntityDescription):
    """Describes a ClimaCell sensor entity."""

    unit_imperial: str | None = None
    unit_metric: str | None = None
    metric_conversion: Callable[[float], float] | float = 1.0
    is_metric_check: bool | None = None
    device_class: str | None = None
    value_map: IntEnum | None = None

    def __post_init__(self) -> None:
        """Post initialization."""
        units = (self.unit_imperial, self.unit_metric)
        if any(u is not None for u in units) and any(u is None for u in units):
            raise RuntimeError(
                "`unit_imperial` and `unit_metric` both need to be None or both need "
                "to be defined."
            )


# V3 constants
CONDITIONS_V3 = {
    "breezy": ATTR_CONDITION_WINDY,
    "freezing_rain_heavy": ATTR_CONDITION_SNOWY_RAINY,
    "freezing_rain": ATTR_CONDITION_SNOWY_RAINY,
    "freezing_rain_light": ATTR_CONDITION_SNOWY_RAINY,
    "freezing_drizzle": ATTR_CONDITION_SNOWY_RAINY,
    "ice_pellets_heavy": ATTR_CONDITION_HAIL,
    "ice_pellets": ATTR_CONDITION_HAIL,
    "ice_pellets_light": ATTR_CONDITION_HAIL,
    "snow_heavy": ATTR_CONDITION_SNOWY,
    "snow": ATTR_CONDITION_SNOWY,
    "snow_light": ATTR_CONDITION_SNOWY,
    "flurries": ATTR_CONDITION_SNOWY,
    "tstorm": ATTR_CONDITION_LIGHTNING,
    "rain_heavy": ATTR_CONDITION_POURING,
    "rain": ATTR_CONDITION_RAINY,
    "rain_light": ATTR_CONDITION_RAINY,
    "drizzle": ATTR_CONDITION_RAINY,
    "fog_light": ATTR_CONDITION_FOG,
    "fog": ATTR_CONDITION_FOG,
    "cloudy": ATTR_CONDITION_CLOUDY,
    "mostly_cloudy": ATTR_CONDITION_CLOUDY,
    "partly_cloudy": ATTR_CONDITION_PARTLYCLOUDY,
}

# Weather attributes
CC_V3_ATTR_TIMESTAMP = "observation_time"
CC_V3_ATTR_TEMPERATURE = "temp"
CC_V3_ATTR_TEMPERATURE_HIGH = "max"
CC_V3_ATTR_TEMPERATURE_LOW = "min"
CC_V3_ATTR_PRESSURE = "baro_pressure"
CC_V3_ATTR_HUMIDITY = "humidity"
CC_V3_ATTR_WIND_SPEED = "wind_speed"
CC_V3_ATTR_WIND_DIRECTION = "wind_direction"
CC_V3_ATTR_OZONE = "o3"
CC_V3_ATTR_CONDITION = "weather_code"
CC_V3_ATTR_VISIBILITY = "visibility"
CC_V3_ATTR_PRECIPITATION = "precipitation"
CC_V3_ATTR_PRECIPITATION_DAILY = "precipitation_accumulation"
CC_V3_ATTR_PRECIPITATION_PROBABILITY = "precipitation_probability"
CC_V3_ATTR_WIND_GUST = "wind_gust"
CC_V3_ATTR_CLOUD_COVER = "cloud_cover"
CC_V3_ATTR_PRECIPITATION_TYPE = "precipitation_type"

# Sensor attributes
CC_V3_ATTR_PARTICULATE_MATTER_25 = "pm25"
CC_V3_ATTR_PARTICULATE_MATTER_10 = "pm10"
CC_V3_ATTR_NITROGEN_DIOXIDE = "no2"
CC_V3_ATTR_CARBON_MONOXIDE = "co"
CC_V3_ATTR_SULFUR_DIOXIDE = "so2"
CC_V3_ATTR_EPA_AQI = "epa_aqi"
CC_V3_ATTR_EPA_PRIMARY_POLLUTANT = "epa_primary_pollutant"
CC_V3_ATTR_EPA_HEALTH_CONCERN = "epa_health_concern"
CC_V3_ATTR_CHINA_AQI = "china_aqi"
CC_V3_ATTR_CHINA_PRIMARY_POLLUTANT = "china_primary_pollutant"
CC_V3_ATTR_CHINA_HEALTH_CONCERN = "china_health_concern"
CC_V3_ATTR_POLLEN_TREE = "pollen_tree"
CC_V3_ATTR_POLLEN_WEED = "pollen_weed"
CC_V3_ATTR_POLLEN_GRASS = "pollen_grass"
CC_V3_ATTR_FIRE_INDEX = "fire_index"

CC_V3_SENSOR_TYPES = (
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_OZONE,
        name="Ozone",
        unit_imperial=CONCENTRATION_PARTS_PER_BILLION,
        unit_metric=CONCENTRATION_PARTS_PER_BILLION,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_PARTICULATE_MATTER_25,
        name="Particulate Matter < 2.5 μm",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=3.2808399**3,
        is_metric_check=False,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_PARTICULATE_MATTER_10,
        name="Particulate Matter < 10 μm",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=3.2808399**3,
        is_metric_check=False,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_NITROGEN_DIOXIDE,
        name="Nitrogen Dioxide",
        unit_imperial=CONCENTRATION_PARTS_PER_BILLION,
        unit_metric=CONCENTRATION_PARTS_PER_BILLION,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_CARBON_MONOXIDE,
        name="Carbon Monoxide",
        unit_imperial=CONCENTRATION_PARTS_PER_MILLION,
        unit_metric=CONCENTRATION_PARTS_PER_MILLION,
        device_class=SensorDeviceClass.CO,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_SULFUR_DIOXIDE,
        name="Sulfur Dioxide",
        unit_imperial=CONCENTRATION_PARTS_PER_BILLION,
        unit_metric=CONCENTRATION_PARTS_PER_BILLION,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_EPA_AQI,
        name="US EPA Air Quality Index",
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_EPA_PRIMARY_POLLUTANT,
        name="US EPA Primary Pollutant",
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_EPA_HEALTH_CONCERN,
        name="US EPA Health Concern",
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_CHINA_AQI,
        name="China MEP Air Quality Index",
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_CHINA_PRIMARY_POLLUTANT,
        name="China MEP Primary Pollutant",
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_CHINA_HEALTH_CONCERN,
        name="China MEP Health Concern",
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_POLLEN_TREE,
        name="Tree Pollen Index",
        value_map=V3PollenIndex,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_POLLEN_WEED,
        name="Weed Pollen Index",
        value_map=V3PollenIndex,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_POLLEN_GRASS,
        name="Grass Pollen Index",
        value_map=V3PollenIndex,
    ),
    ClimaCellSensorEntityDescription(
        key=CC_V3_ATTR_FIRE_INDEX,
        name="Fire Index",
    ),
)
