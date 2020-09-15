"""Constants for the ClimaCell integration."""
CONF_FORECAST_TYPE = "forecast_type"
CONF_AQI_COUNTRY = "aqi_country"
CONF_TIMESTEP = "timestep"

DISABLE_FORECASTS = "disable"
DAILY = "daily"
HOURLY = "hourly"
NOWCAST = "nowcast"
USA = "usa"
CHINA = "china"

CURRENT = "current"
FORECASTS = "forecasts"

DEFAULT_NAME = "ClimaCell"
DEFAULT_TIMESTEP = 15
DEFAULT_FORECAST_TYPE = DAILY
DEFAULT_AQI_COUNTRY = USA
DOMAIN = "climacell"
ATTRIBUTION = "Powered by ClimaCell"

MAX_REQUESTS_PER_DAY = 1000

AQI_FIELD_LOOKUP = {USA: "epa_aqi", CHINA: "china_aqi"}

CONDITIONS = {
    "freezing_rain_heavy": "snowy-rainy",
    "freezing_rain": "snowy-rainy",
    "freezing_rain_light": "snowy-rainy",
    "freezing_drizzle": "snowy-rainy",
    "ice_pellets_heavy": "hail",
    "ice_pellets": "hail",
    "ice_pellets_light": "hail",
    "snow_heavy": "snowy",
    "snow": "snowy",
    "snow_light": "snowy",
    "flurries": "snowy",
    "tstorm": "lightning",
    "rain_heavy": "pouring",
    "rain": "rainy",
    "rain_light": "rainy",
    "drizzle": "rainy",
    "fog_light": "fog",
    "fog": "fog",
    "cloudy": "cloudy",
    "mostly_cloudy": "cloudy",
    "partly_cloudy": "partlycloudy",
}

CLEAR_CONDITIONS = {"night": "clear-night", "day": "sunny"}

CC_ATTR_TIMESTAMP = "observation_time"
CC_ATTR_TEMPERATURE = "temp"
CC_ATTR_TEMPERATURE_HIGH = "max"
CC_ATTR_TEMPERATURE_LOW = "min"
CC_ATTR_PRESSURE = "baro_pressure"
CC_ATTR_HUMIDITY = "humidity"
CC_ATTR_WIND_SPEED = "wind_speed"
CC_ATTR_WIND_DIRECTION = "wind_direction"
CC_ATTR_OZONE = "o3"
CC_ATTR_CONDITION = "weather_code"
CC_ATTR_VISIBILITY = "visibility"
CC_ATTR_PRECIPITATION = "precipitation"
CC_ATTR_PRECIPITATION_DAILY = "precipitation_accumulation"
CC_ATTR_PRECIPITATION_PROBABILITY = "precipitation_probability"
CC_ATTR_PM_2_5 = "pm25"
CC_ATTR_PM_10 = "pm10"
CC_ATTR_CARBON_MONOXIDE = "co"
CC_ATTR_SULPHUR_DIOXIDE = "so2"
CC_ATTR_NITROGEN_DIOXIDE = "no2"
