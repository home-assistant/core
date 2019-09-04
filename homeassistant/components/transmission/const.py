"""Constants for the Transmission Bittorent Client component."""
DOMAIN = "transmission"
DATA_UPDATED = "transmission_data_updated"
DATA_TRANSMISSION = "data_transmission"


CONF_TURTLE_MODE = "turtle_mode"
CONF_SENSOR_TYPES = {
    "active_torrents": ["Active Torrents", None, False],
    "current_status": ["Status", None, True],
    "download_speed": ["Down Speed", "MB/s", False],
    "paused_torrents": ["Paused Torrents", None, False],
    "total_torrents": ["Total Torrents", None, False],
    "upload_speed": ["Up Speed", "MB/s", False],
    "completed_torrents": ["Completed Torrents", None, False],
    "started_torrents": ["Started Torrents", None, False],
}

ATTR_TORRENT = "torrent"

SERVICE_ADD_TORRENT = "add_torrent"
