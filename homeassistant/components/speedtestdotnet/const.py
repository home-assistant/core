"""Consts used by Speedtest.net."""

from homeassistant.const import DATA_RATE_MEGABITS_PER_SECOND

DOMAIN = "speedtestdotnet"
DATA_UPDATED = f"{DOMAIN}_data_updated"

SENSOR_TYPES = {
    "ping": ["Ping", "ms"],
    "download": ["Download", DATA_RATE_MEGABITS_PER_SECOND],
    "upload": ["Upload", DATA_RATE_MEGABITS_PER_SECOND],
}
