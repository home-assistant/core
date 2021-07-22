"""Consts used by Speedtest.net."""
from typing import Final

from homeassistant.const import DATA_RATE_MEGABITS_PER_SECOND, TIME_MILLISECONDS

DOMAIN: Final = "speedtestdotnet"

SPEED_TEST_SERVICE: Final = "speedtest"

SENSOR_TYPES: Final = {
    "ping": ["Ping", TIME_MILLISECONDS],
    "download": ["Download", DATA_RATE_MEGABITS_PER_SECOND],
    "upload": ["Upload", DATA_RATE_MEGABITS_PER_SECOND],
}

CONF_SERVER_NAME: Final = "server_name"
CONF_SERVER_ID: Final = "server_id"
CONF_MANUAL: Final = "manual"

ATTR_BYTES_RECEIVED: Final = "bytes_received"
ATTR_BYTES_SENT: Final = "bytes_sent"
ATTR_SERVER_COUNTRY: Final = "server_country"
ATTR_SERVER_ID: Final = "server_id"
ATTR_SERVER_NAME: Final = "server_name"


DEFAULT_NAME: Final = "SpeedTest"
DEFAULT_SCAN_INTERVAL: Final = 60
DEFAULT_SERVER: Final = "*Auto Detect"

ATTRIBUTION: Final = "Data retrieved from Speedtest.net by Ookla"

ICON: Final = "mdi:speedometer"

PLATFORMS: Final = ["sensor"]
