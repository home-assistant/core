"""Constants for Xiaomi Weather."""

from datetime import timedelta

DOMAIN = "xiaomi_weather"
CONF_CITY_ID = "city_id"
UPDATE_INTERVAL = timedelta(minutes=15)

CONDITIONS = {
    "0": "sunny",
    "1": "partlycloudy",
    "2": "cloudy",
    "3": "rainy",
    "4": "lightning-rainy",
    "5": "hail",
    "6": "snowy-rainy",
    "7": "rainy",
    "8": "rainy",
    "9": "pouring",
    "10": "pouring",
    "11": "pouring",
    "12": "pouring",
    "13": "snowy",
    "14": "snowy",
    "15": "snowy",
    "16": "snowy",
    "17": "snowy",
    "18": "fog",
    "19": "snowy-rainy",
    "20": "exceptional",
    "21": "rainy",
    "22": "pouring",
    "23": "pouring",
    "24": "pouring",
    "25": "pouring",
    "26": "snowy",
    "27": "snowy",
    "28": "snowy",
    "29": "exceptional",
    "30": "exceptional",
    "31": "exceptional",
    "53": "fog",
}
