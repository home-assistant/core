"""Constants for the Transmission Bittorent Client component."""
DOMAIN = "transmission"

SENSOR_TYPES = {
    "active_torrents": ["Active Torrents", None, None],
    "current_status": ["Status", None, None],
    "download_speed": ["Down Speed", "MB/s", None],
    "paused_torrents": ["Paused Torrents", None, None],
    "total_torrents": ["Total Torrents", None, None],
    "upload_speed": ["Up Speed", "MB/s", None],
    "completed_torrents": ["Completed Torrents", None, None],
    "started_torrents": ["Started Torrents", None, None],
    "torrent_down_list": ["Downloading", None, None],
    "started_torrent_dict": ["Torrent Info", None, None],
}
SWITCH_TYPES = {"on_off": "Switch", "turtle_mode": "Turtle Mode"}

DEFAULT_NAME = "Transmission"
DEFAULT_PORT = 9091
DEFAULT_SCAN_INTERVAL = 120

STATE_ATTR_TORRENT_INFO = "torrent_info"
SERVICE_ADD_TORRENT = "add_torrent"

DATA_UPDATED = "transmission_data_updated"
<<<<<<< HEAD
=======
DATA_TRANSMISSION = "data_transmission"

_TRPC = {
    "check pending": "check pending",
    "checking": "checking",
    "downloading": "downloading",
    "seeding": "seeding",
    "stopped": "stopped",
    "download pending": "download pending",
    "seed pending": "seed pending",
}
>>>>>>> Add information about current downloads.
