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

GET_TORRENT_STATES_RESPONSE = {
    "6dcd3f46d09547b62bf07ba9b2943c95d53ddae3": {b"state": b"Seeding"},
    "1c56ea49918b9baed94cf4bc0ee9f324efc8841a": {b"state": b"Downloading"},
    "fbf4dab701189a344fa5ab06d7b87c11a74e3da0": {b"state": b"Seeding"},
}
