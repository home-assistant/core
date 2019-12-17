"""Constants for the Transmission Bittorent Client component."""
DOMAIN = "transmission"

SENSOR_TYPES = {
    "active_torrents": ["Active Torrents", "Counts"],
    "current_status": ["Status", None],
    "download_speed": ["Down Speed", "MB/s"],
    "paused_torrents": ["Paused Torrents", "Counts"],
    "total_torrents": ["Total Torrents", "Counts"],
    "upload_speed": ["Up Speed", "MB/s"],
    "completed_torrents": ["Completed Torrents", "Counts"],
    "started_torrents": ["Started Torrents", "Counts"],
}
SWITCH_TYPES = {"on_off": "Switch", "turtle_mode": "Turtle Mode"}

DEFAULT_NAME = "Transmission"
DEFAULT_PORT = 9091
DEFAULT_SCAN_INTERVAL = 120

STATE_ATTR_TORRENT_INFO = "torrent_info"
ATTR_TORRENT = "torrent"
SERVICE_ADD_TORRENT = "add_torrent"

DATA_UPDATED = "transmission_data_updated"
