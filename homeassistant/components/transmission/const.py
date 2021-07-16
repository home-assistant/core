"""Constants for the Transmission Bittorent Client component."""
from typing import Final

DOMAIN: Final = "transmission"

SWITCH_TYPES: Final = {"on_off": "Switch", "turtle_mode": "Turtle Mode"}

ORDER_NEWEST_FIRST: Final = "newest_first"
ORDER_OLDEST_FIRST: Final = "oldest_first"
ORDER_BEST_RATIO_FIRST: Final = "best_ratio_first"
ORDER_WORST_RATIO_FIRST: Final = "worst_ratio_first"

SUPPORTED_ORDER_MODES: Final = {
    ORDER_NEWEST_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t.addedDate, reverse=True
    ),
    ORDER_OLDEST_FIRST: lambda torrents: sorted(torrents, key=lambda t: t.addedDate),
    ORDER_WORST_RATIO_FIRST: lambda torrents: sorted(torrents, key=lambda t: t.ratio),
    ORDER_BEST_RATIO_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t.ratio, reverse=True
    ),
}

CONF_LIMIT: Final = "limit"
CONF_ORDER: Final = "order"

DEFAULT_DELETE_DATA: Final = False
DEFAULT_LIMIT: Final = 10
DEFAULT_ORDER: Final = ORDER_OLDEST_FIRST
DEFAULT_NAME: Final = "Transmission"
DEFAULT_PORT: Final = 9091
DEFAULT_SCAN_INTERVAL: Final = 120

STATE_ATTR_TORRENT_INFO: Final = "torrent_info"

ATTR_DELETE_DATA: Final = "delete_data"
ATTR_TORRENT: Final = "torrent"

SERVICE_ADD_TORRENT: Final = "add_torrent"
SERVICE_REMOVE_TORRENT: Final = "remove_torrent"
SERVICE_START_TORRENT: Final = "start_torrent"
SERVICE_STOP_TORRENT: Final = "stop_torrent"

EVENT_STARTED_TORRENT: Final = "transmission_started_torrent"
EVENT_REMOVED_TORRENT: Final = "transmission_removed_torrent"
EVENT_DOWNLOADED_TORRENT: Final = "transmission_downloaded_torrent"

PLATFORMS: Final = ["sensor", "switch"]
