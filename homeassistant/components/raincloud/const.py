"""Support for Melnor RainCloud sprinkler water timer."""

DATA_RAINCLOUD = "raincloud"

ICON_MAP = {
    "auto_watering": "mdi:autorenew",
    "battery": "",
    "is_watering": "",
    "manual_watering": "mdi:water-pump",
    "next_cycle": "mdi:calendar-clock",
    "rain_delay": "mdi:weather-rainy",
    "status": "",
    "watering_time": "mdi:water-pump",
}


SIGNAL_UPDATE_RAINCLOUD = "raincloud_update"
