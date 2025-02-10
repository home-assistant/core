"""Tests for the Deluge integration."""

from homeassistant.components.deluge.const import (
    CONF_WEB_PORT,
    DEFAULT_RPC_PORT,
    DEFAULT_WEB_PORT,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME

CONF_DATA = {
    CONF_HOST: "1.2.3.4",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "password",
    CONF_PORT: DEFAULT_RPC_PORT,
    CONF_WEB_PORT: DEFAULT_WEB_PORT,
}

GET_TORRENT_STATUS_RESPONSE = {
    "upload_rate": 3462.0,
    "download_rate": 98.5,
    "dht_upload_rate": 7818.0,
    "dht_download_rate": 2658.0,
}
