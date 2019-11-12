"""Constants for the Deluge Client component."""
DOMAIN = "deluge"

ATTR_TORRENT = "torrent"

DEFAULT_NAME = "Deluge"
DELUGE_SWITCH = "Switch"
DEFAULT_PORT = 58846
DEFAULT_SCAN_INTERVAL = 120

DHT_UPLOAD = 1000
DHT_DOWNLOAD = 1000

SERVICE_ADD_TORRENT = "add_torrent"

DATA_UPDATED = "deluge_data_updated"

SENSOR_TYPES = {
    "active_torrents": ["Active Torrents", None],
    "current_status": ["Status", None],
    "download_speed": ["Down Speed", "MB/s"],
    "paused_torrents": ["Paused Torrents", None],
    "total_torrents": ["Total Torrents", None],
    "upload_speed": ["Up Speed", "MB/s"],
    "completed_torrents": ["Completed Torrents", None],
    "started_torrents": ["Started Torrents", None],
}
