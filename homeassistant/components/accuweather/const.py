"""Constants for AccuWeather integration."""
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_METERS,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
    UNIT_PERCENTAGE,
    UV_INDEX,
    VOLUME_CUBIC_METERS,
)

ATTRIBUTION = "Data provided by AccuWeather"
ATTR_ICON = "icon"
ATTR_FORECAST = CONF_FORECAST = "forecast"
ATTR_LABEL = "label"
ATTR_UNIT_IMPERIAL = "Imperial"
ATTR_UNIT_METRIC = "Metric"
CONCENTRATION_PARTS_PER_CUBIC_METER = f"p/{VOLUME_CUBIC_METERS}"
COORDINATOR = "coordinator"
DOMAIN = "accuweather"
LENGTH_MILIMETERS = "mm"
MANUFACTURER = "AccuWeather, Inc."
NAME = "AccuWeather"
UNDO_UPDATE_LISTENER = "undo_update_listener"

CONDITION_CLASSES = {
    "clear-night": [33, 34, 37],
    "cloudy": [7, 8, 38],
    "exceptional": [24, 30, 31],
    "fog": [11],
    "hail": [25],
    "lightning": [15],
    "lightning-rainy": [16, 17, 41, 42],
    "partlycloudy": [4, 6, 35, 36],
    "pouring": [18],
    "rainy": [12, 13, 14, 26, 39, 40],
    "snowy": [19, 20, 21, 22, 23, 43, 44],
    "snowy-rainy": [29],
    "sunny": [1, 2, 3, 5],
    "windy": [32],
}

FORECAST_DAYS = [0, 1, 2, 3, 4]

FORECAST_SENSOR_TYPES = {
    "CloudCoverDay": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-cloudy",
        ATTR_LABEL: "Cloud Cover Day",
        ATTR_UNIT_METRIC: UNIT_PERCENTAGE,
        ATTR_UNIT_IMPERIAL: UNIT_PERCENTAGE,
    },
    "CloudCoverNight": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-cloudy",
        ATTR_LABEL: "Cloud Cover Night",
        ATTR_UNIT_METRIC: UNIT_PERCENTAGE,
        ATTR_UNIT_IMPERIAL: UNIT_PERCENTAGE,
    },
    "Grass": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:grass",
        ATTR_LABEL: "Grass Pollen",
        ATTR_UNIT_METRIC: CONCENTRATION_PARTS_PER_CUBIC_METER,
        ATTR_UNIT_IMPERIAL: CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "HoursOfSun": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-partly-cloudy",
        ATTR_LABEL: "Hours Of Sun",
        ATTR_UNIT_METRIC: TIME_HOURS,
        ATTR_UNIT_IMPERIAL: TIME_HOURS,
    },
    "Mold": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:blur",
        ATTR_LABEL: "Mold Pollen",
        ATTR_UNIT_METRIC: CONCENTRATION_PARTS_PER_CUBIC_METER,
        ATTR_UNIT_IMPERIAL: CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "Ozone": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:vector-triangle",
        ATTR_LABEL: "Ozone",
        ATTR_UNIT_METRIC: None,
        ATTR_UNIT_IMPERIAL: None,
    },
    "Ragweed": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:sprout",
        ATTR_LABEL: "Ragweed Pollen",
        ATTR_UNIT_METRIC: CONCENTRATION_PARTS_PER_CUBIC_METER,
        ATTR_UNIT_IMPERIAL: CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "RealFeelTemperatureMax": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "RealFeel Temperature Max",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureMin": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "RealFeel Temperature Min",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureShadeMax": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "RealFeel Temperature Shade Max",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureShadeMin": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "RealFeel Temperature Shade Min",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "ThunderstormProbabilityDay": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-lightning",
        ATTR_LABEL: "Thunderstorm Probability Day",
        ATTR_UNIT_METRIC: UNIT_PERCENTAGE,
        ATTR_UNIT_IMPERIAL: UNIT_PERCENTAGE,
    },
    "ThunderstormProbabilityNight": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-lightning",
        ATTR_LABEL: "Thunderstorm Probability Night",
        ATTR_UNIT_METRIC: UNIT_PERCENTAGE,
        ATTR_UNIT_IMPERIAL: UNIT_PERCENTAGE,
    },
    "Tree": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:tree-outline",
        ATTR_LABEL: "Tree Pollen",
        ATTR_UNIT_METRIC: CONCENTRATION_PARTS_PER_CUBIC_METER,
        ATTR_UNIT_IMPERIAL: CONCENTRATION_PARTS_PER_CUBIC_METER,
    },
    "UVIndex": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-sunny",
        ATTR_LABEL: "UV Index",
        ATTR_UNIT_METRIC: UV_INDEX,
        ATTR_UNIT_IMPERIAL: UV_INDEX,
    },
    "WindGustDay": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Gust Day",
        ATTR_UNIT_METRIC: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_IMPERIAL: SPEED_MILES_PER_HOUR,
    },
    "WindGustNight": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Gust Night",
        ATTR_UNIT_METRIC: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_IMPERIAL: SPEED_MILES_PER_HOUR,
    },
}

OPTIONAL_SENSORS = (
    "ApparentTemperature",
    "CloudCover",
    "CloudCoverDay",
    "CloudCoverNight",
    "DewPoint",
    "Grass",
    "Mold",
    "Ozone",
    "Ragweed",
    "RealFeelTemperatureShade",
    "RealFeelTemperatureShadeMax",
    "RealFeelTemperatureShadeMin",
    "Tree",
    "WetBulbTemperature",
    "WindChillTemperature",
    "WindGust",
    "WindGustDay",
    "WindGustNight",
)

SENSOR_TYPES = {
    "ApparentTemperature": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Apparent Temperature",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "Ceiling": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-fog",
        ATTR_LABEL: "Cloud Ceiling",
        ATTR_UNIT_METRIC: LENGTH_METERS,
        ATTR_UNIT_IMPERIAL: LENGTH_FEET,
    },
    "CloudCover": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-cloudy",
        ATTR_LABEL: "Cloud Cover",
        ATTR_UNIT_METRIC: UNIT_PERCENTAGE,
        ATTR_UNIT_IMPERIAL: UNIT_PERCENTAGE,
    },
    "DewPoint": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Dew Point",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "RealFeelTemperature": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "RealFeel Temperature",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "RealFeelTemperatureShade": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "RealFeel Temperature Shade",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "Precipitation": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-rainy",
        ATTR_LABEL: "Precipitation",
        ATTR_UNIT_METRIC: LENGTH_MILIMETERS,
        ATTR_UNIT_IMPERIAL: LENGTH_INCHES,
    },
    "PressureTendency": {
        ATTR_DEVICE_CLASS: "accuweather__pressure_tendency",
        ATTR_ICON: "mdi:gauge",
        ATTR_LABEL: "Pressure Tendency",
        ATTR_UNIT_METRIC: None,
        ATTR_UNIT_IMPERIAL: None,
    },
    "UVIndex": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-sunny",
        ATTR_LABEL: "UV Index",
        ATTR_UNIT_METRIC: UV_INDEX,
        ATTR_UNIT_IMPERIAL: UV_INDEX,
    },
    "WetBulbTemperature": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Wet Bulb Temperature",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "WindChillTemperature": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Wind Chill Temperature",
        ATTR_UNIT_METRIC: TEMP_CELSIUS,
        ATTR_UNIT_IMPERIAL: TEMP_FAHRENHEIT,
    },
    "WindGust": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Gust",
        ATTR_UNIT_METRIC: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_IMPERIAL: SPEED_MILES_PER_HOUR,
    },
}
