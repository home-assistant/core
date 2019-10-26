"""Consts used by Speedtest.net."""

DEFAULT_NAME = "SpeedTest"
DEFAULT_SCAN_INTERVAL = 60
DOMAIN = "speedtestdotnet"
DATA_UPDATED = f"{DOMAIN}_data_updated"

SENSOR_TYPES = {
    "ping": ["Ping", "ms"],
    "download": ["Download", "Mbit/s"],
    "upload": ["Upload", "Mbit/s"],
}

CONF_SERVER_ID = "server_id"
CONF_MANUAL = "manual"
