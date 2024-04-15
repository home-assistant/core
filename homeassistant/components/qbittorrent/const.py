"""Constants for qBittorrent."""

from typing import Final

DOMAIN: Final = "qbittorrent"

DEFAULT_NAME = "qBittorrent"
DEFAULT_URL = "http://127.0.0.1:8080"

STATE_ATTR_TORRENT_INFO = "torrent_info"
STATE_ATTR_ALL_TORRENT_INFO = "all_torrent_info"

STATE_UP_DOWN = "up_down"
STATE_SEEDING = "seeding"
STATE_DOWNLOADING = "downloading"

SERVICE_GET_TORRENTS = "get_torrents"
SERVICE_GET_ALL_TORRENTS = "get_all_torrents"
TORRENT_FILTER = "torrent_filter"
