"""Consts used by Speedtest.net."""

DEFAULT_NAME = "SpeedTest"
DEFAULT_SCAN_INTERVAL = 60
DOMAIN = "speedtestdotnet"
SPEED_TEST_SERVICE = "speedtest"
DATA_UPDATED = f"{DOMAIN}_data_updated"

SENSOR_TYPES = {
    "ping": ["Ping", "ms"],
    "download": ["Download", "Mbit/s"],
    "upload": ["Upload", "Mbit/s"],
}

CONF_SERVER_ID = "server_id"
CONF_MANUAL = "manual"

ATTR_BYTES_RECEIVED = "bytes_received"
ATTR_BYTES_SENT = "bytes_sent"
ATTR_SERVER_COUNTRY = "server_country"
ATTR_SERVER_ID = "server_id"
ATTR_SERVER_LATENCY = "latency"
ATTR_SERVER_NAME = "server_name"

ATTRIBUTION = "Data retrieved from Speedtest.net by Ookla"

ICON = "mdi:speedometer"
