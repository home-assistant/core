"""Constants for the Transmission Bittorrent Client component."""

from __future__ import annotations

from collections.abc import Callable

from transmission_rpc import Torrent

DOMAIN = "transmission"

ORDER_NEWEST_FIRST = "newest_first"
ORDER_OLDEST_FIRST = "oldest_first"
ORDER_BEST_RATIO_FIRST = "best_ratio_first"
ORDER_WORST_RATIO_FIRST = "worst_ratio_first"

SUPPORTED_ORDER_MODES: dict[str, Callable[[list[Torrent]], list[Torrent]]] = {
    ORDER_NEWEST_FIRST: lambda torrents: sorted(
        torrents, key=lambda t: t.added_date, reverse=True
    ),
    ORDER_OLDEST_FIRST: lambda torrents: sorted(torrents, key=lambda t: t.added_date),
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
DEFAULT_SSL = False
DEFAULT_PORT = 9091
DEFAULT_PATH = "/transmission/rpc"
DEFAULT_SCAN_INTERVAL = 120

STATE_ATTR_TORRENT_INFO = "torrent_info"

ATTR_DELETE_DATA = "delete_data"
ATTR_TORRENT = "torrent"

SERVICE_ADD_TORRENT = "add_torrent"
SERVICE_REMOVE_TORRENT = "remove_torrent"
SERVICE_START_TORRENT = "start_torrent"
SERVICE_STOP_TORRENT = "stop_torrent"

EVENT_STARTED_TORRENT = "transmission_started_torrent"
EVENT_REMOVED_TORRENT = "transmission_removed_torrent"
EVENT_DOWNLOADED_TORRENT = "transmission_downloaded_torrent"

STATE_UP_DOWN = "up_down"
STATE_SEEDING = "seeding"
STATE_DOWNLOADING = "downloading"
