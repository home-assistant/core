"""Constants for the ClimaCell integration."""
from pyclimacell.const import (
    DAILY,
    HOURLY,
    NOWCAST,
    HealthConcernType,
    PollenIndex,
    PrimaryPollutantType,
    V3PollenIndex,
    WeatherCode,
)

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
    ATTR_NAME,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
)

CONF_TIMESTEP = "timestep"
FORECAST_TYPES = [DAILY, HOURLY, NOWCAST]

DEFAULT_NAME = "ClimaCell"
DEFAULT_TIMESTEP = 15
DEFAULT_FORECAST_TYPE = DAILY
DOMAIN = "climacell"
ATTRIBUTION = "Powered by ClimaCell"

MAX_REQUESTS_PER_DAY = 500

CLEAR_CONDITIONS = {"night": ATTR_CONDITION_CLEAR_NIGHT, "day": ATTR_CONDITION_SUNNY}

MAX_FORECASTS = {
    DAILY: 14,
    HOURLY: 24,
    NOWCAST: 30,
}

# Sensor type keys
ATTR_FIELD = "field"
ATTR_METRIC_CONVERSION = "metric_conversion"
ATTR_VALUE_MAP = "value_map"
ATTR_IS_METRIC_CHECK = "is_metric_check"

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

CC_SENSOR_TYPES = [
    {
        ATTR_FIELD: CC_ATTR_PARTICULATE_MATTER_25,
        ATTR_NAME: "Particulate Matter < 2.5 μm",
        CONF_UNIT_SYSTEM_IMPERIAL: "μg/ft³",
        CONF_UNIT_SYSTEM_METRIC: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_METRIC_CONVERSION: 3.2808399 ** 3,
        ATTR_IS_METRIC_CHECK: True,
    },
    {
        ATTR_FIELD: CC_ATTR_PARTICULATE_MATTER_10,
        ATTR_NAME: "Particulate Matter < 10 μm",
        CONF_UNIT_SYSTEM_IMPERIAL: "μg/ft³",
        CONF_UNIT_SYSTEM_METRIC: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_METRIC_CONVERSION: 3.2808399 ** 3,
        ATTR_IS_METRIC_CHECK: True,
    },
    {
        ATTR_FIELD: CC_ATTR_NITROGEN_DIOXIDE,
        ATTR_NAME: "Nitrogen Dioxide",
        CONF_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
    },
    {
        ATTR_FIELD: CC_ATTR_CARBON_MONOXIDE,
        ATTR_NAME: "Carbon Monoxide",
        CONF_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
    },
    {
        ATTR_FIELD: CC_ATTR_SULFUR_DIOXIDE,
        ATTR_NAME: "Sulfur Dioxide",
        CONF_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
    },
    {ATTR_FIELD: CC_ATTR_EPA_AQI, ATTR_NAME: "US EPA Air Quality Index"},
    {
        ATTR_FIELD: CC_ATTR_EPA_PRIMARY_POLLUTANT,
        ATTR_NAME: "US EPA Primary Pollutant",
        ATTR_VALUE_MAP: PrimaryPollutantType,
    },
    {
        ATTR_FIELD: CC_ATTR_EPA_HEALTH_CONCERN,
        ATTR_NAME: "US EPA Health Concern",
        ATTR_VALUE_MAP: HealthConcernType,
    },
    {ATTR_FIELD: CC_ATTR_CHINA_AQI, ATTR_NAME: "China MEP Air Quality Index"},
    {
        ATTR_FIELD: CC_ATTR_CHINA_PRIMARY_POLLUTANT,
        ATTR_NAME: "China MEP Primary Pollutant",
        ATTR_VALUE_MAP: PrimaryPollutantType,
    },
    {
        ATTR_FIELD: CC_ATTR_CHINA_HEALTH_CONCERN,
        ATTR_NAME: "China MEP Health Concern",
        ATTR_VALUE_MAP: HealthConcernType,
    },
    {
        ATTR_FIELD: CC_ATTR_POLLEN_TREE,
        ATTR_NAME: "Tree Pollen Index",
        ATTR_VALUE_MAP: PollenIndex,
    },
    {
        ATTR_FIELD: CC_ATTR_POLLEN_WEED,
        ATTR_NAME: "Weed Pollen Index",
        ATTR_VALUE_MAP: PollenIndex,
    },
    {
        ATTR_FIELD: CC_ATTR_POLLEN_GRASS,
        ATTR_NAME: "Grass Pollen Index",
        ATTR_VALUE_MAP: PollenIndex,
    },
    {ATTR_FIELD: CC_ATTR_FIRE_INDEX, ATTR_NAME: "Fire Index"},
]

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

CC_V3_SENSOR_TYPES = [
    {
        ATTR_FIELD: CC_V3_ATTR_PARTICULATE_MATTER_25,
        ATTR_NAME: "Particulate Matter < 2.5 μm",
        CONF_UNIT_SYSTEM_IMPERIAL: "μg/ft³",
        CONF_UNIT_SYSTEM_METRIC: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_METRIC_CONVERSION: 1 / (3.2808399 ** 3),
        ATTR_IS_METRIC_CHECK: False,
    },
    {
        ATTR_FIELD: CC_V3_ATTR_PARTICULATE_MATTER_10,
        ATTR_NAME: "Particulate Matter < 10 μm",
        CONF_UNIT_SYSTEM_IMPERIAL: "μg/ft³",
        CONF_UNIT_SYSTEM_METRIC: CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        ATTR_METRIC_CONVERSION: 1 / (3.2808399 ** 3),
        ATTR_IS_METRIC_CHECK: False,
    },
    {
        ATTR_FIELD: CC_V3_ATTR_NITROGEN_DIOXIDE,
        ATTR_NAME: "Nitrogen Dioxide",
        CONF_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
    },
    {
        ATTR_FIELD: CC_V3_ATTR_CARBON_MONOXIDE,
        ATTR_NAME: "Carbon Monoxide",
        CONF_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_MILLION,
    },
    {
        ATTR_FIELD: CC_V3_ATTR_SULFUR_DIOXIDE,
        ATTR_NAME: "Sulfur Dioxide",
        CONF_UNIT_OF_MEASUREMENT: CONCENTRATION_PARTS_PER_BILLION,
    },
    {ATTR_FIELD: CC_V3_ATTR_EPA_AQI, ATTR_NAME: "US EPA Air Quality Index"},
    {
        ATTR_FIELD: CC_V3_ATTR_EPA_PRIMARY_POLLUTANT,
        ATTR_NAME: "US EPA Primary Pollutant",
    },
    {ATTR_FIELD: CC_V3_ATTR_EPA_HEALTH_CONCERN, ATTR_NAME: "US EPA Health Concern"},
    {ATTR_FIELD: CC_V3_ATTR_CHINA_AQI, ATTR_NAME: "China MEP Air Quality Index"},
    {
        ATTR_FIELD: CC_V3_ATTR_CHINA_PRIMARY_POLLUTANT,
        ATTR_NAME: "China MEP Primary Pollutant",
    },
    {
        ATTR_FIELD: CC_V3_ATTR_CHINA_HEALTH_CONCERN,
        ATTR_NAME: "China MEP Health Concern",
    },
    {
        ATTR_FIELD: CC_V3_ATTR_POLLEN_TREE,
        ATTR_NAME: "Tree Pollen Index",
        ATTR_VALUE_MAP: V3PollenIndex,
    },
    {
        ATTR_FIELD: CC_V3_ATTR_POLLEN_WEED,
        ATTR_NAME: "Weed Pollen Index",
        ATTR_VALUE_MAP: V3PollenIndex,
    },
    {
        ATTR_FIELD: CC_V3_ATTR_POLLEN_GRASS,
        ATTR_NAME: "Grass Pollen Index",
        ATTR_VALUE_MAP: V3PollenIndex,
    },
    {ATTR_FIELD: CC_V3_ATTR_FIRE_INDEX, ATTR_NAME: "Fire Index"},
]
