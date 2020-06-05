"""Constants for the ClimaCell integration."""
CONF_FORECAST_FREQUENCY = "forecast_frequency"
CONF_AQI_COUNTRY = "aqi_country"

DISABLE_FORECASTS = "(Disable Forecasts)"
DAILY = "Daily"
HOURLY = "Hourly"
USA = "USA"
CHINA = "China"

CURRENT = "current"
FORECASTS = "forecasts"

DEFAULT_NAME = "climacell"
DOMAIN = "climacell"
ATTRIBUTION = (
    "Powered by ClimaCell Weather API " "(https://www.climacell.co/weather-api/)"
)

MAX_REQUESTS_PER_DAY = 1000

ATTR_WEATHER_CLOUD_COVER = "cloud_cover"
ATTR_WEATHER_DEWPOINT = "dewpoint"
ATTR_WEATHER_FEELS_LIKE = "feels_like"
ATTR_WEATHER_MOON_PHASE = "moon_phase"
ATTR_WEATHER_PRECIPITATION = "precipitation"
ATTR_WEATHER_PRECIPITATION_TYPE = "precipitation_type"
ATTR_WEATHER_WIND_GUST = "wind_gust"

AQI_FIELD_LOOKUP = {USA.lower(): "epa_aqi", CHINA.lower(): "china_aqi"}

DIRECTIONS_LIST = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]

WIND_DIRECTIONS = {name: idx * 360 / 16 for idx, name in enumerate(DIRECTIONS_LIST)}

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
