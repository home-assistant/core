"""Constants for the Deluge integration."""

import logging
from typing import Final

CONF_WEB_PORT = "web_port"
CURRENT_STATUS = "current_status"
DATA_KEYS = ["upload_rate", "download_rate", "dht_upload_rate", "dht_download_rate"]
DEFAULT_NAME = "Deluge"
DEFAULT_RPC_PORT = 58846
DEFAULT_WEB_PORT = 8112
DOMAIN: Final = "deluge"
DOWNLOAD_SPEED = "download_speed"

LOGGER = logging.getLogger(__package__)

UPLOAD_SPEED = "upload_speed"
