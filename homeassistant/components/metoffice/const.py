"""Constants for Met Office Integration."""

from datetime import timedelta

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
)

DOMAIN = "metoffice"

DEFAULT_NAME = "Met Office"
ATTRIBUTION = "Data provided by the Met Office"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

METOFFICE_COORDINATES = "metoffice_coordinates"
METOFFICE_HOURLY_COORDINATOR = "metoffice_hourly_coordinator"
METOFFICE_TWICE_DAILY_COORDINATOR = "metoffice_twice_daily_coordinator"
METOFFICE_DAILY_COORDINATOR = "metoffice_daily_coordinator"
METOFFICE_MONITORED_CONDITIONS = "metoffice_monitored_conditions"
METOFFICE_NAME = "metoffice_name"

CONDITION_CLASSES: dict[str, list[int]] = {
    ATTR_CONDITION_CLEAR_NIGHT: [0],
    ATTR_CONDITION_CLOUDY: [7, 8],
    ATTR_CONDITION_FOG: [5, 6],
    ATTR_CONDITION_HAIL: [19, 20, 21],
    ATTR_CONDITION_LIGHTNING: [30],
    ATTR_CONDITION_LIGHTNING_RAINY: [28, 29],
    ATTR_CONDITION_PARTLYCLOUDY: [2, 3],
    ATTR_CONDITION_POURING: [13, 14, 15],
    ATTR_CONDITION_RAINY: [9, 10, 11, 12],
    ATTR_CONDITION_SNOWY: [22, 23, 24, 25, 26, 27],
    ATTR_CONDITION_SNOWY_RAINY: [16, 17, 18],
    ATTR_CONDITION_SUNNY: [1],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}

HOURLY_FORECAST_ATTRIBUTE_MAP: dict[str, str] = {
    ATTR_FORECAST_CONDITION: "significantWeatherCode",
    ATTR_FORECAST_NATIVE_APPARENT_TEMP: "feelsLikeTemperature",
    ATTR_FORECAST_NATIVE_PRESSURE: "mslp",
    ATTR_FORECAST_NATIVE_TEMP: "screenTemperature",
    ATTR_FORECAST_PRECIPITATION: "totalPrecipAmount",
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: "probOfPrecipitation",
    ATTR_FORECAST_UV_INDEX: "uvIndex",
    ATTR_FORECAST_WIND_BEARING: "windDirectionFrom10m",
    ATTR_FORECAST_NATIVE_WIND_SPEED: "windSpeed10m",
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: "windGustSpeed10m",
}

DAY_FORECAST_ATTRIBUTE_MAP: dict[str, str] = {
    ATTR_FORECAST_CONDITION: "daySignificantWeatherCode",
    ATTR_FORECAST_NATIVE_APPARENT_TEMP: "dayMaxFeelsLikeTemp",
    ATTR_FORECAST_NATIVE_PRESSURE: "middayMslp",
    ATTR_FORECAST_NATIVE_TEMP: "dayUpperBoundMaxTemp",
    ATTR_FORECAST_NATIVE_TEMP_LOW: "dayLowerBoundMaxTemp",
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: "dayProbabilityOfPrecipitation",
    ATTR_FORECAST_UV_INDEX: "maxUvIndex",
    ATTR_FORECAST_WIND_BEARING: "midday10MWindDirection",
    ATTR_FORECAST_NATIVE_WIND_SPEED: "midday10MWindSpeed",
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: "midday10MWindGust",
}

NIGHT_FORECAST_ATTRIBUTE_MAP: dict[str, str] = {
    ATTR_FORECAST_CONDITION: "nightSignificantWeatherCode",
    ATTR_FORECAST_NATIVE_APPARENT_TEMP: "nightMinFeelsLikeTemp",
    ATTR_FORECAST_NATIVE_PRESSURE: "midnightMslp",
    ATTR_FORECAST_NATIVE_TEMP: "nightUpperBoundMinTemp",
    ATTR_FORECAST_NATIVE_TEMP_LOW: "nightLowerBoundMinTemp",
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: "nightProbabilityOfPrecipitation",
    ATTR_FORECAST_WIND_BEARING: "midnight10MWindDirection",
    ATTR_FORECAST_NATIVE_WIND_SPEED: "midnight10MWindSpeed",
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: "midnight10MWindGust",
}

DAILY_FORECAST_ATTRIBUTE_MAP: dict[str, str] = {
    ATTR_FORECAST_CONDITION: "daySignificantWeatherCode",
    ATTR_FORECAST_NATIVE_APPARENT_TEMP: "dayMaxFeelsLikeTemp",
    ATTR_FORECAST_NATIVE_PRESSURE: "middayMslp",
    ATTR_FORECAST_NATIVE_TEMP: "dayMaxScreenTemperature",
    ATTR_FORECAST_NATIVE_TEMP_LOW: "nightMinScreenTemperature",
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: "dayProbabilityOfPrecipitation",
    ATTR_FORECAST_UV_INDEX: "maxUvIndex",
    ATTR_FORECAST_WIND_BEARING: "midday10MWindDirection",
    ATTR_FORECAST_NATIVE_WIND_SPEED: "midday10MWindSpeed",
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: "midday10MWindGust",
}
