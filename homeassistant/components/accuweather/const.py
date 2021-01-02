"""Constants for AccuWeather integration."""
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
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_METERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
    UV_INDEX,
)

ATTRIBUTION = "Data provided by AccuWeather"
ATTR_ICON = "icon"
ATTR_FORECAST = CONF_FORECAST = "forecast"
ATTR_LABEL = "label"
ATTR_UNIT_IMPERIAL = "Imperial"
ATTR_UNIT_METRIC = "Metric"
COORDINATOR = "coordinator"
DOMAIN = "accuweather"
MANUFACTURER = "AccuWeather, Inc."
NAME = "AccuWeather"
UNDO_UPDATE_LISTENER = "undo_update_listener"

CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT: [33, 34, 37],
    ATTR_CONDITION_CLOUDY: [7, 8, 38],
    ATTR_CONDITION_EXCEPTIONAL: [24, 30, 31],
    ATTR_CONDITION_FOG: [11],
    ATTR_CONDITION_HAIL: [25],
    ATTR_CONDITION_LIGHTNING: [15],
    ATTR_CONDITION_LIGHTNING_RAINY: [16, 17, 41, 42],
    ATTR_CONDITION_PARTLYCLOUDY: [3, 4, 6, 35, 36],
    ATTR_CONDITION_POURING: [18],
    ATTR_CONDITION_RAINY: [12, 13, 14, 26, 39, 40],
    ATTR_CONDITION_SNOWY: [19, 20, 21, 22, 23, 43, 44],
    ATTR_CONDITION_SNOWY_RAINY: [29],
    ATTR_CONDITION_SUNNY: [1, 2, 5],
    ATTR_CONDITION_WINDY: [32],
}

FORECAST_DAYS = [0, 1, 2, 3, 4]

FORECAST_SENSOR_TYPES = {
    "CloudCoverDay": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-cloudy",
        ATTR_LABEL: "Cloud Cover Day",
        ATTR_UNIT_METRIC: PERCENTAGE,
        ATTR_UNIT_IMPERIAL: PERCENTAGE,
    },
    "CloudCoverNight": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-cloudy",
        ATTR_LABEL: "Cloud Cover Night",
        ATTR_UNIT_METRIC: PERCENTAGE,
        ATTR_UNIT_IMPERIAL: PERCENTAGE,
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
        ATTR_UNIT_METRIC: PERCENTAGE,
        ATTR_UNIT_IMPERIAL: PERCENTAGE,
    },
    "ThunderstormProbabilityNight": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-lightning",
        ATTR_LABEL: "Thunderstorm Probability Night",
        ATTR_UNIT_METRIC: PERCENTAGE,
        ATTR_UNIT_IMPERIAL: PERCENTAGE,
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
    "WindDay": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Day",
        ATTR_UNIT_METRIC: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_IMPERIAL: SPEED_MILES_PER_HOUR,
    },
    "WindNight": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Night",
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
        ATTR_UNIT_METRIC: PERCENTAGE,
        ATTR_UNIT_IMPERIAL: PERCENTAGE,
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
        ATTR_UNIT_METRIC: LENGTH_MILLIMETERS,
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
    "Wind": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind",
        ATTR_UNIT_METRIC: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_IMPERIAL: SPEED_MILES_PER_HOUR,
    },
    "WindGust": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Gust",
        ATTR_UNIT_METRIC: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_IMPERIAL: SPEED_MILES_PER_HOUR,
    },
}
