"""Constants for AccuWeather integration."""
ATTRIBUTION = "Data provided by AccuWeather"
ATTR_FORECAST = CONF_FORECAST = "forecast"
COORDINATOR = "coordinator"
DOMAIN = "accuweather"
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
