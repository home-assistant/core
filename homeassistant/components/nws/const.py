"""Constants for National Weather Service Integration."""
DOMAIN = "nws"

CONF_STATION = "station"

ATTRIBUTION = "Data from National Weather Service/NOAA"

ATTR_FORECAST_DETAILED_DESCRIPTION = "detailed_description"
ATTR_FORECAST_PRECIP_PROB = "precipitation_probability"
ATTR_FORECAST_DAYTIME = "daytime"

CONDITION_CLASSES = {
    "exceptional": [
        "Tornado",
        "Hurricane conditions",
        "Tropical storm conditions",
        "Dust",
        "Smoke",
        "Haze",
        "Hot",
        "Cold",
    ],
    "snowy": ["Snow", "Sleet", "Blizzard"],
    "snowy-rainy": [
        "Rain/snow",
        "Rain/sleet",
        "Freezing rain/snow",
        "Freezing rain",
        "Rain/freezing rain",
    ],
    "hail": [],
    "lightning-rainy": [
        "Thunderstorm (high cloud cover)",
        "Thunderstorm (medium cloud cover)",
        "Thunderstorm (low cloud cover)",
    ],
    "lightning": [],
    "pouring": [],
    "rainy": [
        "Rain",
        "Rain showers (high cloud cover)",
        "Rain showers (low cloud cover)",
    ],
    "windy-variant": ["Mostly cloudy and windy", "Overcast and windy"],
    "windy": [
        "Fair/clear and windy",
        "A few clouds and windy",
        "Partly cloudy and windy",
    ],
    "fog": ["Fog/mist"],
    "clear": ["Fair/clear"],  # sunny and clear-night
    "cloudy": ["Mostly cloudy", "Overcast"],
    "partlycloudy": ["A few clouds", "Partly cloudy"],
}

DAYNIGHT = "daynight"
HOURLY = "hourly"

NWS_DATA = "nws data"
COORDINATOR_OBSERVATION = "coordinator_observation"
COORDINATOR_FORECAST = "coordinator_forecast"
COORDINATOR_FORECAST_HOURLY = "coordinator_forecast_hourly"
