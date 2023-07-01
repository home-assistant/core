"""Constants for the Transmission Bittorent Client component."""
DOMAIN = "transmission"

SWITCH_TYPES = {"on_off": "Switch", "turtle_mode": "Turtle Mode"}

ORDER_NEWEST_FIRST = "newest_first"
ORDER_OLDEST_FIRST = "oldest_first"
ORDER_BEST_RATIO_FIRST = "best_ratio_first"
ORDER_WORST_RATIO_FIRST = "worst_ratio_first"

SUPPORTED_ORDER_MODES = {
    ORDER_NEWEST_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t.date_added, reverse=True
    ),
    ORDER_OLDEST_FIRST: lambda torrents: sorted(torrents, key=lambda t: t.date_added),
    ORDER_WORST_RATIO_FIRST: lambda torrents: sorted(torrents, key=lambda t: t.ratio),
    ORDER_BEST_RATIO_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t.ratio, reverse=True
    ),
}
CONF_ENTRY_ID = "entry_id"
CONF_LIMIT = "limit"
CONF_ORDER = "order"

DEFAULT_DELETE_DATA = False
DEFAULT_LIMIT = 10
DEFAULT_ORDER = ORDER_OLDEST_FIRST
DEFAULT_NAME = "Transmission"
DEFAULT_PORT = 9091
DEFAULT_SCAN_INTERVAL = 120

STATE_ATTR_TORRENT_INFO = "torrent_info"

ATTR_DELETE_DATA = "delete_data"
ATTR_TORRENT = "torrent"

SERVICE_ADD_TORRENT = "add_torrent"
SERVICE_REMOVE_TORRENT = "remove_torrent"
SERVICE_START_TORRENT = "start_torrent"
SERVICE_STOP_TORRENT = "stop_torrent"

DATA_UPDATED = "transmission_data_updated"

EVENT_STARTED_TORRENT = "transmission_started_torrent"
EVENT_REMOVED_TORRENT = "transmission_removed_torrent"
EVENT_DOWNLOADED_TORRENT = "transmission_downloaded_torrent"

STATE_UP_DOWN = "up_down"
STATE_SEEDING = "seeding"
STATE_DOWNLOADING = "downloading"
