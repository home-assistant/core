"""Constants for the HERE Destination Weather service."""
from __future__ import annotations

import math

from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    LENGTH_CENTIMETERS,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    PRESSURE_MBAR,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)

DOMAIN = "here_weather"

DEFAULT_SCAN_INTERVAL = 300

FREEMIUM_REQUESTS_PER_MONTH = 250000
MAX_UPDATE_RATE_FOR_ONE_CLIENT = math.ceil(
    (31 * 24 * 3600) / FREEMIUM_REQUESTS_PER_MONTH
)

MODE_ASTRONOMY = "forecast_astronomy"
MODE_HOURLY = "forecast_hourly"
MODE_DAILY = "forecast_7days"
MODE_DAILY_SIMPLE = "forecast_7days_simple"
MODE_OBSERVATION = "observation"
CONF_MODES = [
    MODE_ASTRONOMY,
    MODE_HOURLY,
    MODE_DAILY,
    MODE_DAILY_SIMPLE,
    MODE_OBSERVATION,
]
DEFAULT_MODE = MODE_DAILY_SIMPLE

ASTRONOMY_ATTRIBUTES: dict[str, dict[str, str | None]] = {
    "sunrise": {"name": "Sunrise", "unit_of_measurement": None, "device_class": None},
    "sunset": {"name": "Sunset", "unit_of_measurement": None, "device_class": None},
    "moonrise": {"name": "Moonrise", "unit_of_measurement": None, "device_class": None},
    "moonset": {"name": "Moonset", "unit_of_measurement": None, "device_class": None},
    "moonPhase": {
        "name": "Moon Phase",
        "unit_of_measurement": PERCENTAGE,
        "device_class": None,
    },
    "moonPhaseDesc": {
        "name": "Moon Phase Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "city": {"name": "City", "unit_of_measurement": None, "device_class": None},
    "latitude": {"name": "Latitude", "unit_of_measurement": None, "device_class": None},
    "longitude": {
        "name": "Longitude",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "utcTime": {
        "name": "UTC Time",
        "unit_of_measurement": None,
        "device_class": DEVICE_CLASS_TIMESTAMP,
    },
}

COMMON_ATTRIBUTES: dict[str, dict[str, str | None]] = {
    "daylight": {"name": "Daylight", "unit_of_measurement": None, "device_class": None},
    "description": {
        "name": "Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "skyInfo": {"name": "Sky Info", "unit_of_measurement": None, "device_class": None},
    "skyDescription": {
        "name": "Sky Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "temperatureDesc": {
        "name": "Temperature Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "comfort": {
        "name": "Comfort",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "humidity": {
        "name": "Humidity",
        "unit_of_measurement": PERCENTAGE,
        "device_class": DEVICE_CLASS_HUMIDITY,
    },
    "dewPoint": {
        "name": "Dew Point",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "precipitationProbability": {
        "name": "Precipitation Probability",
        "unit_of_measurement": PERCENTAGE,
        "device_class": None,
    },
    "precipitationDesc": {
        "name": "Precipitation Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "airDescription": {
        "name": "Air Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "windSpeed": {
        "name": "Wind Speed",
        "unit_of_measurement": SPEED_KILOMETERS_PER_HOUR,
        "device_class": None,
    },
    "windDirection": {
        "name": "Wind Direction",
        "unit_of_measurement": DEGREE,
        "device_class": None,
    },
    "windDesc": {
        "name": "Wind Description",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "windDescShort": {
        "name": "Wind Description Short",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "icon": {"name": "Icon", "unit_of_measurement": None, "device_class": None},
    "iconName": {
        "name": "Icon Name",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "iconLink": {
        "name": "Icon Link",
        "unit_of_measurement": None,
        "device_class": None,
    },
}

NON_OBSERVATION_ATTRIBUTES: dict[str, dict[str, str | None]] = {
    "rainFall": {
        "name": "Rain Fall",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "snowFall": {
        "name": "Snow Fall",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "precipitationProbability": {
        "name": "Precipitation Probability",
        "unit_of_measurement": PERCENTAGE,
        "device_class": None,
    },
    "dayOfWeek": {
        "name": "Day of Week",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "weekday": {"name": "Week Day", "unit_of_measurement": None, "device_class": None},
    "utcTime": {
        "name": "UTC Time",
        "unit_of_measurement": None,
        "device_class": DEVICE_CLASS_TIMESTAMP,
    },
    **COMMON_ATTRIBUTES,
}

HOURLY_ATTRIBUTES: dict[str, dict[str, str | None]] = {
    "temperature": {
        "name": "Temperature",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "airInfo": {"name": "Air Info", "unit_of_measurement": None, "device_class": None},
    "visibility": {
        "name": "Visibility",
        "unit_of_measurement": LENGTH_KILOMETERS,
        "device_class": None,
    },
    **NON_OBSERVATION_ATTRIBUTES,
}

DAILY_SIMPLE_ATTRIBUTES: dict[str, dict[str, str | None]] = {
    "highTemperature": {
        "name": "High Temperature",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "lowTemperature": {
        "name": "Low Temperature",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "beaufortScale": {
        "name": "Beaufort Scale",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "beaufortDescription": {
        "name": "Beaufort Scale Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "uvIndex": {"name": "UV Index", "unit_of_measurement": None, "device_class": None},
    "uvDesc": {
        "name": "UV Index Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "barometerPressure": {
        "name": "Barometric Pressure",
        "unit_of_measurement": PRESSURE_MBAR,
        "device_class": DEVICE_CLASS_PRESSURE,
    },
    **NON_OBSERVATION_ATTRIBUTES,
}

DAILY_ATTRIBUTES: dict[str, dict[str, str | None]] = {
    "daySegment": {
        "name": "Day Segment",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "temperature": {
        "name": "Temperature",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "beaufortScale": {
        "name": "Beaufort Scale",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "beaufortDescription": {
        "name": "Beaufort Scale Description",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "visibility": {
        "name": "Visibility",
        "unit_of_measurement": LENGTH_KILOMETERS,
        "device_class": None,
    },
    **NON_OBSERVATION_ATTRIBUTES,
}

OBSERVATION_ATTRIBUTES: dict[str, dict[str, str | None]] = {
    "temperature": {
        "name": "Temperature",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "highTemperature": {
        "name": "High Temperature",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "lowTemperature": {
        "name": "Low Temperature",
        "unit_of_measurement": TEMP_CELSIUS,
        "device_class": DEVICE_CLASS_TEMPERATURE,
    },
    "precipitation1H": {
        "name": "Precipitation Over 1 Hour",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "precipitation3H": {
        "name": "Precipitation Over 3 Hours",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "precipitation6H": {
        "name": "Precipitation Over 6 Hours",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "precipitation12H": {
        "name": "Precipitation Over 12 Hours",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "precipitation24H": {
        "name": "Precipitation Over 24 Hours",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "barometerPressure": {
        "name": "Barometric Pressure",
        "unit_of_measurement": PRESSURE_MBAR,
        "device_class": DEVICE_CLASS_PRESSURE,
    },
    "barometerTrend": {
        "name": "Barometric Pressure Trend",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "visibility": {
        "name": "Visibility",
        "unit_of_measurement": LENGTH_KILOMETERS,
        "device_class": None,
    },
    "snowCover": {
        "name": "Snow Cover",
        "unit_of_measurement": LENGTH_CENTIMETERS,
        "device_class": None,
    },
    "activeAlerts": {
        "name": "Active Alerts",
        "unit_of_measurement": None,
        "device_class": None,
    },
    "country": {"name": "Country", "unit_of_measurement": None, "device_class": None},
    "state": {"name": "State", "unit_of_measurement": None, "device_class": None},
    "city": {"name": "City", "unit_of_measurement": None, "device_class": None},
    **COMMON_ATTRIBUTES,
}

SENSOR_TYPES: dict[str, dict[str, dict[str, str | None]]] = {
    MODE_ASTRONOMY: ASTRONOMY_ATTRIBUTES,
    MODE_HOURLY: HOURLY_ATTRIBUTES,
    MODE_DAILY_SIMPLE: DAILY_SIMPLE_ATTRIBUTES,
    MODE_DAILY: DAILY_ATTRIBUTES,
    MODE_OBSERVATION: OBSERVATION_ATTRIBUTES,
}

CONDITION_CLASSES: dict[str, list[str]] = {
    "clear-night": [
        "night_passing_clouds",
        "night_mostly_clear",
        "night_clearing_skies",
        "night_clear",
    ],
    "cloudy": [
        "night_decreasing_cloudiness",
        "night_mostly_cloudy",
        "night_morning_clouds",
        "night_afternoon_clouds",
        "night_high_clouds",
        "night_high_level_clouds",
        "low_clouds",
        "overcast",
        "cloudy",
        "afternoon_clouds",
        "morning_clouds",
        "high_level_clouds",
        "high_clouds",
    ],
    "fog": [
        "night_low_level_haze",
        "night_smoke",
        "night_haze",
        "dense_fog",
        "fog",
        "light_fog",
        "early_fog",
        "early_fog_followed_by_sunny_skies",
        "low_level_haze",
        "smoke",
        "haze",
        "ice_fog",
        "hazy_sunshine",
    ],
    "hail": ["hail"],
    "lightning": [
        "night_tstorms",
        "night_scattered_tstorms",
        "scattered_tstorms",
        "night_a_few_tstorms",
        "night_isolated_tstorms",
        "night_widely_scattered_tstorms",
        "tstorms_early",
        "isolated_tstorms_late",
        "scattered_tstorms_late",
        "widely_scattered_tstorms",
        "isolated_tstorms",
        "a_few_tstorms",
    ],
    "lightning-rainy": ["thundershowers", "thunderstorms", "tstorms_late", "tstorms"],
    "partlycloudy": [
        "partly_sunny",
        "mostly_cloudy",
        "broken_clouds",
        "more_clouds_than_sun",
        "night_broken_clouds",
        "increasing_cloudiness",
        "night_partly_cloudy",
        "night_scattered_clouds",
        "passing_clounds",
        "more_sun_than_clouds",
        "scattered_clouds",
        "partly_cloudy",
        "a_mixture_of_sun_and_clouds",
        "increasing_cloudiness",
        "decreasing_cloudiness",
        "clearing_skies",
        "breaks_of_sun_late",
    ],
    "pouring": [
        "heavy_rain_late",
        "heavy_rain_early",
        "tons_of_rain",
        "lots_of_rain",
        "heavy_rain",
        "heavy_rain_early",
        "heavy_rain_early",
    ],
    "rainy": [
        "rain_late",
        "showers_late",
        "rain_early",
        "showery",
        "showers_early",
        "numerous_showers",
        "rain",
        "light_rain_late",
        "sprinkles_late",
        "light_rain_early",
        "sprinkles_early",
        "light_rain",
        "sprinkles",
        "drizzle",
        "night_showers",
        "night_sprinkles",
        "night_rain_showers",
        "night_passing_showers",
        "night_light_showers",
        "night_a_few_showers",
        "night_scattered_showers",
        "rain_early",
        "scattered_showers",
        "a_few_showers",
        "light_showers",
        "passing_showers",
        "rain_showers",
        "showers",
    ],
    "snowy": [
        "heavy_snow_late",
        "heavy_snow_early",
        "heavy_snow",
        "snow_late",
        "snow_early",
        "moderate_snow",
        "snow",
        "light_snow_late",
        "snow_showers_late",
        "flurries_late",
        "light_snow_early",
        "flurries_early",
        "light_snow",
        "snow_flurries",
        "sleet",
        "an_icy_mix_changing_to_snow",
        "an_icy_mix_changing_to_rain",
        "rain_changing_to_snow",
        "icy_mix_early",
        "light_icy_mix_late",
        "icy_mix_late",
        "scattered_flurries",
    ],
    "snowy-rainy": [
        "freezing_rain",
        "light_freezing_rain",
        "snow_showers_early",
        "snow_showers",
        "light_snow_showers",
        "snow_rain_mix",
        "light_icy_mix_early",
        "rain_changing_to_an_icy_mix",
        "snow_changing_to_an_icy_mix",
        "snow_changing_to_rain",
        "heavy_mixture_of_precip",
        "light_mixture_of_precip",
        "icy_mix",
        "mixture_of_precip",
    ],
    "sunny": ["sunny", "clear", "mostly_sunny", "mostly_clear"],
    "windy": ["strong_thunderstorms", "severe_thunderstorms"],
    "windy-variant": [],
    "exceptional": [
        "blizzard",
        "snowstorm",
        "duststorm",
        "sandstorm",
        "hurricane",
        "tropical_storm",
        "flood",
        "flash_floods",
        "tornado",
    ],
}
