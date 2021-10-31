"""Constants for the Deluge integration."""

from datetime import timedelta

CONF_WEB_PORT = "web_port"
DATA_KEY_API = "api"
DATA_KEY_COORDINATOR = "coordinator"
DEFAULT_NAME = "Deluge"
DEFAULT_RPC_PORT = 58846
DEFAULT_WEB_PORT = 8112
DHT_UPLOAD = 1000
DHT_DOWNLOAD = 1000
DOMAIN = "deluge"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
