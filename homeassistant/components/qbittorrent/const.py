"""Constants for qBittorrent."""

from typing import Final

DOMAIN: Final = "qbittorrent"

DEFAULT_NAME = "qBittorrent"
DEFAULT_URL = "http://127.0.0.1:8080"

STATE_ATTR_TORRENTS = "torrents"
STATE_ATTR_ALL_TORRENTS = "all_torrents"

STATE_UP_DOWN = "up_down"
STATE_SEEDING = "seeding"
STATE_DOWNLOADING = "downloading"
