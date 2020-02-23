"""Consts used by Speedtest.net."""

from homeassistant.const import DATA_RATE_MEGABITS_PER_SECOND, TIME_MILLISECONDS

DOMAIN = "speedtestdotnet"
DATA_UPDATED = f"{DOMAIN}_data_updated"

SENSOR_TYPES = {
    "ping": ["Ping", TIME_MILLISECONDS],
    "download": ["Download", DATA_RATE_MEGABITS_PER_SECOND],
    "upload": ["Upload", DATA_RATE_MEGABITS_PER_SECOND],
}
