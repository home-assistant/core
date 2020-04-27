"""Constants for the Transmission Bittorent Client component."""

DOMAIN = "transmission"

SWITCH_TYPES = {"on_off": "Switch", "turtle_mode": "Turtle Mode"}

DEFAULT_DELETE_DATA = False
DEFAULT_NAME = "Transmission"
DEFAULT_PORT = 9091
DEFAULT_SCAN_INTERVAL = 120

STATE_ATTR_TORRENT_INFO = "torrent_info"

ATTR_DELETE_DATA = "delete_data"
ATTR_TORRENT = "torrent"

SERVICE_ADD_TORRENT = "add_torrent"
SERVICE_REMOVE_TORRENT = "remove_torrent"

DATA_UPDATED = "transmission_data_updated"

EVENT_STARTED_TORRENT = "transmission_started_torrent"
EVENT_REMOVED_TORRENT = "transmission_removed_torrent"
EVENT_DOWNLOADED_TORRENT = "transmission_downloaded_torrent"
