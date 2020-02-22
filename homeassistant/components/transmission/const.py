"""Constants for the Transmission Bittorent Client component."""

from homeassistant.const import DATA_RATE_MEGABYTES_PER_SECOND

DOMAIN = "transmission"

SENSOR_TYPES = {
    "active_torrents": ["Active Torrents", "Torrents"],
    "current_status": ["Status", None],
    "download_speed": ["Down Speed", DATA_RATE_MEGABYTES_PER_SECOND],
    "paused_torrents": ["Paused Torrents", "Torrents"],
    "total_torrents": ["Total Torrents", "Torrents"],
    "upload_speed": ["Up Speed", DATA_RATE_MEGABYTES_PER_SECOND],
    "completed_torrents": ["Completed Torrents", "Torrents"],
    "started_torrents": ["Started Torrents", "Torrents"],
}
SWITCH_TYPES = {"on_off": "Switch", "turtle_mode": "Turtle Mode"}

DEFAULT_NAME = "Transmission"
DEFAULT_PORT = 9091
DEFAULT_SCAN_INTERVAL = 120

STATE_ATTR_TORRENT_INFO = "torrent_info"
ATTR_TORRENT = "torrent"
SERVICE_ADD_TORRENT = "add_torrent"

DATA_UPDATED = "transmission_data_updated"
