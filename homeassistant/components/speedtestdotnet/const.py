"""Consts used by Speedtest.net."""
from homeassistant.const import DATA_RATE_MEGABITS_PER_SECOND, TIME_MILLISECONDS

DOMAIN = "speedtestdotnet"

SPEED_TEST_SERVICE = "speedtest"
DATA_UPDATED = f"{DOMAIN}_data_updated"

SENSOR_TYPES = {
    "ping": ["Ping", TIME_MILLISECONDS],
    "download": ["Download", DATA_RATE_MEGABITS_PER_SECOND],
    "upload": ["Upload", DATA_RATE_MEGABITS_PER_SECOND],
}

CONF_SERVER_NAME = "server_name"
CONF_SERVER_ID = "server_id"
CONF_MANUAL = "manual"

ATTR_BYTES_RECEIVED = "bytes_received"
ATTR_BYTES_SENT = "bytes_sent"
ATTR_SERVER_COUNTRY = "server_country"
ATTR_SERVER_ID = "server_id"
ATTR_SERVER_NAME = "server_name"


DEFAULT_NAME = "SpeedTest"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_SERVER = "*Auto Detect"

ATTRIBUTION = "Data retrieved from Speedtest.net by Ookla"

ICON = "mdi:speedometer"
