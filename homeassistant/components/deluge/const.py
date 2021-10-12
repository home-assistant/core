"""Constants for the Deluge Bittorent Client component."""
DOMAIN = "deluge"

ORDER_NEWEST_FIRST = "newest_first"
ORDER_OLDEST_FIRST = "oldest_first"
ORDER_BEST_RATIO_FIRST = "best_ratio_first"
ORDER_WORST_RATIO_FIRST = "worst_ratio_first"

SUPPORTED_ORDER_MODES = {
    ORDER_NEWEST_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t[b"time_added"], reverse=True
    ),
    ORDER_OLDEST_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t[b"time_added"]
    ),
    ORDER_WORST_RATIO_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t[b"ratio"]
    ),
    ORDER_BEST_RATIO_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t[b"ratio"], reverse=True
    ),
}

CONF_LIMIT = "limit"
CONF_ORDER = "order"

DEFAULT_DELETE_DATA = False
DEFAULT_LIMIT = 10
DEFAULT_ORDER = ORDER_OLDEST_FIRST
DEFAULT_NAME = "Deluge"
DEFAULT_PORT = 58846
DEFAULT_SCAN_INTERVAL = 120

STATE_ATTR_FREE_SPACE = "free_space"
STATE_ATTR_TORRENT_INFO = "torrent_info"

ATTR_DELETE_DATA = "delete_data"
ATTR_TORRENT = "torrent"

SERVICE_ADD_TORRENT = "add_torrent"
SERVICE_RESUME_TORRENT = "resume_torrent"
SERVICE_PAUSE_TORRENT = "pause_torrent"
SERVICE_REMOVE_TORRENT = "remove_torrent"

DATA_UPDATED = "deluge_data_updated"

EVENT_STARTED_TORRENT = "deluge_started_torrent"
EVENT_FINISHED_TORRENT = "deluge_finished_torrent"

EVENT_ADDED_TORRENT = "deluge_added_torrent"
EVENT_REMOVED_TORRENT = "deluge_removed_torrent"
