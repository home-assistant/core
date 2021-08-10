"""Constants for the Tomorrow.io integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pytomorrowio.const import (
    DAILY,
    HOURLY,
    NOWCAST,
    HealthConcernType,
    PollenIndex,
    PrecipitationType,
    PrimaryPollutantType,
    WeatherCode,
)

from homeassistant.components.sensor import SensorEntityDescription
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
    DEVICE_CLASS_CO,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    IRRADIATION_BTUS_PER_HOUR_SQUARE_FOOT,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.util.distance import convert as distance_convert
from homeassistant.util.pressure import convert as pressure_convert
from homeassistant.util.temperature import convert as temp_convert

CONF_TIMESTEP = "timestep"
FORECAST_TYPES = [DAILY, HOURLY, NOWCAST]

DEFAULT_TIMESTEP = 15
DEFAULT_FORECAST_TYPE = DAILY
DOMAIN = "tomorrowio"
INTEGRATION_NAME = "Tomorrow.io"
DEFAULT_NAME = INTEGRATION_NAME
ATTRIBUTION = "Powered by Tomorrow.io"

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

# V4 constants
CONDITIONS = {
    WeatherCode.WIND: ATTR_CONDITION_WINDY,
    WeatherCode.LIGHT_WIND: ATTR_CONDITION_WINDY,
    WeatherCode.STRONG_WIND: ATTR_CONDITION_WINDY,
    WeatherCode.FREEZING_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.HEAVY_FREEZING_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.LIGHT_FREEZING_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.FREEZING_DRIZZLE: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.ICE_PELLETS: ATTR_CONDITION_HAIL,
    WeatherCode.HEAVY_ICE_PELLETS: ATTR_CONDITION_HAIL,
    WeatherCode.LIGHT_ICE_PELLETS: ATTR_CONDITION_HAIL,
    WeatherCode.SNOW: ATTR_CONDITION_SNOWY,
    WeatherCode.HEAVY_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCode.LIGHT_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCode.FLURRIES: ATTR_CONDITION_SNOWY,
    WeatherCode.THUNDERSTORM: ATTR_CONDITION_LIGHTNING,
    WeatherCode.RAIN: ATTR_CONDITION_POURING,
    WeatherCode.HEAVY_RAIN: ATTR_CONDITION_RAINY,
    WeatherCode.LIGHT_RAIN: ATTR_CONDITION_RAINY,
    WeatherCode.DRIZZLE: ATTR_CONDITION_RAINY,
    WeatherCode.FOG: ATTR_CONDITION_FOG,
    WeatherCode.LIGHT_FOG: ATTR_CONDITION_FOG,
    WeatherCode.CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCode.MOSTLY_CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCode.PARTLY_CLOUDY: ATTR_CONDITION_PARTLYCLOUDY,
}

# Weather constants
CC_ATTR_TIMESTAMP = "startTime"
CC_ATTR_TEMPERATURE = "temperature"
CC_ATTR_TEMPERATURE_HIGH = "temperatureMax"
CC_ATTR_TEMPERATURE_LOW = "temperatureMin"
CC_ATTR_PRESSURE = "pressureSeaLevel"
CC_ATTR_HUMIDITY = "humidity"
CC_ATTR_WIND_SPEED = "windSpeed"
CC_ATTR_WIND_DIRECTION = "windDirection"
CC_ATTR_OZONE = "pollutantO3"
CC_ATTR_CONDITION = "weatherCode"
CC_ATTR_VISIBILITY = "visibility"
CC_ATTR_PRECIPITATION = "precipitationIntensityAvg"
CC_ATTR_PRECIPITATION_PROBABILITY = "precipitationProbability"
CC_ATTR_WIND_GUST = "windGust"
CC_ATTR_CLOUD_COVER = "cloudCover"
CC_ATTR_PRECIPITATION_TYPE = "precipitationType"

# Sensor attributes
CC_ATTR_PARTICULATE_MATTER_25 = "particulateMatter25"
CC_ATTR_PARTICULATE_MATTER_10 = "particulateMatter10"
CC_ATTR_NITROGEN_DIOXIDE = "pollutantNO2"
CC_ATTR_CARBON_MONOXIDE = "pollutantCO"
CC_ATTR_SULFUR_DIOXIDE = "pollutantSO2"
CC_ATTR_EPA_AQI = "epaIndex"
CC_ATTR_EPA_PRIMARY_POLLUTANT = "epaPrimaryPollutant"
CC_ATTR_EPA_HEALTH_CONCERN = "epaHealthConcern"
CC_ATTR_CHINA_AQI = "mepIndex"
CC_ATTR_CHINA_PRIMARY_POLLUTANT = "mepPrimaryPollutant"
CC_ATTR_CHINA_HEALTH_CONCERN = "mepHealthConcern"
CC_ATTR_POLLEN_TREE = "treeIndex"
CC_ATTR_POLLEN_WEED = "weedIndex"
CC_ATTR_POLLEN_GRASS = "grassIndex"
CC_ATTR_FIRE_INDEX = "fireIndex"
CC_ATTR_FEELS_LIKE = "temperatureApparent"
CC_ATTR_DEW_POINT = "dewPoint"
CC_ATTR_PRESSURE_SURFACE_LEVEL = "pressureSurfaceLevel"
CC_ATTR_SOLAR_GHI = "solarGHI"
CC_ATTR_CLOUD_BASE = "cloudBase"
CC_ATTR_CLOUD_CEILING = "cloudCeiling"


@dataclass
class TomorrowioSensorEntityDescription(SensorEntityDescription):
    """Describes a Tomorrow.io sensor entity."""

    unit_imperial: str | None = None
    unit_metric: str | None = None
    metric_conversion: Callable[[float], float] | float = 1.0
    is_metric_check: bool | None = None
    device_class: str | None = None
    value_map: Any | None = None

    def __post_init__(self) -> None:
        """Post initialization."""
        units = (self.unit_imperial, self.unit_metric)
        if any(u is not None for u in units) and any(u is None for u in units):
            raise RuntimeError(
                "`unit_imperial` and `unit_metric` both need to be None or both need "
                "to be defined."
            )


CC_SENSOR_TYPES = (
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_FEELS_LIKE,
        name="Feels Like",
        unit_imperial=TEMP_FAHRENHEIT,
        unit_metric=TEMP_CELSIUS,
        metric_conversion=lambda val: temp_convert(val, TEMP_FAHRENHEIT, TEMP_CELSIUS),
        is_metric_check=True,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_DEW_POINT,
        name="Dew Point",
        unit_imperial=TEMP_FAHRENHEIT,
        unit_metric=TEMP_CELSIUS,
        metric_conversion=lambda val: temp_convert(val, TEMP_FAHRENHEIT, TEMP_CELSIUS),
        is_metric_check=True,
        device_class=DEVICE_CLASS_TEMPERATURE,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_PRESSURE_SURFACE_LEVEL,
        name="Pressure (Surface Level)",
        unit_imperial=PRESSURE_INHG,
        unit_metric=PRESSURE_HPA,
        metric_conversion=lambda val: pressure_convert(
            val, PRESSURE_INHG, PRESSURE_HPA
        ),
        is_metric_check=True,
        device_class=DEVICE_CLASS_PRESSURE,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_SOLAR_GHI,
        name="Global Horizontal Irradiance",
        unit_imperial=IRRADIATION_BTUS_PER_HOUR_SQUARE_FOOT,
        unit_metric=IRRADIATION_WATTS_PER_SQUARE_METER,
        metric_conversion=3.15459,
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_CLOUD_BASE,
        name="Cloud Base",
        unit_imperial=LENGTH_MILES,
        unit_metric=LENGTH_KILOMETERS,
        metric_conversion=lambda val: distance_convert(
            val, LENGTH_MILES, LENGTH_KILOMETERS
        ),
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_CLOUD_CEILING,
        name="Cloud Ceiling",
        unit_imperial=LENGTH_MILES,
        unit_metric=LENGTH_KILOMETERS,
        metric_conversion=lambda val: distance_convert(
            val, LENGTH_MILES, LENGTH_KILOMETERS
        ),
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_CLOUD_COVER,
        name="Cloud Cover",
        unit_imperial=PERCENTAGE,
        unit_metric=PERCENTAGE,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_WIND_GUST,
        name="Wind Gust",
        unit_imperial=SPEED_MILES_PER_HOUR,
        unit_metric=SPEED_METERS_PER_SECOND,
        metric_conversion=lambda val: distance_convert(val, LENGTH_MILES, LENGTH_METERS)
        / 3600,
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_PRECIPITATION_TYPE,
        name="Precipitation Type",
        value_map=PrecipitationType,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_OZONE,
        name="Ozone",
        unit_imperial=CONCENTRATION_PARTS_PER_BILLION,
        unit_metric=CONCENTRATION_PARTS_PER_BILLION,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_PARTICULATE_MATTER_25,
        name="Particulate Matter < 2.5 μm",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=3.2808399 ** 3,
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_PARTICULATE_MATTER_10,
        name="Particulate Matter < 10 μm",
        unit_imperial=CONCENTRATION_MICROGRAMS_PER_CUBIC_FOOT,
        unit_metric=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        metric_conversion=3.2808399 ** 3,
        is_metric_check=True,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_NITROGEN_DIOXIDE,
        name="Nitrogen Dioxide",
        unit_imperial=CONCENTRATION_PARTS_PER_BILLION,
        unit_metric=CONCENTRATION_PARTS_PER_BILLION,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_CARBON_MONOXIDE,
        name="Carbon Monoxide",
        unit_imperial=CONCENTRATION_PARTS_PER_MILLION,
        unit_metric=CONCENTRATION_PARTS_PER_MILLION,
        device_class=DEVICE_CLASS_CO,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_SULFUR_DIOXIDE,
        name="Sulfur Dioxide",
        unit_imperial=CONCENTRATION_PARTS_PER_BILLION,
        unit_metric=CONCENTRATION_PARTS_PER_BILLION,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_EPA_AQI,
        name="US EPA Air Quality Index",
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_EPA_PRIMARY_POLLUTANT,
        name="US EPA Primary Pollutant",
        value_map=PrimaryPollutantType,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_EPA_HEALTH_CONCERN,
        name="US EPA Health Concern",
        value_map=HealthConcernType,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_CHINA_AQI,
        name="China MEP Air Quality Index",
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_CHINA_PRIMARY_POLLUTANT,
        name="China MEP Primary Pollutant",
        value_map=PrimaryPollutantType,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_CHINA_HEALTH_CONCERN,
        name="China MEP Health Concern",
        value_map=HealthConcernType,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_POLLEN_TREE,
        name="Tree Pollen Index",
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_POLLEN_WEED,
        name="Weed Pollen Index",
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        key=CC_ATTR_POLLEN_GRASS,
        name="Grass Pollen Index",
        value_map=PollenIndex,
    ),
    TomorrowioSensorEntityDescription(
        CC_ATTR_FIRE_INDEX,
        name="Fire Index",
    ),
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
