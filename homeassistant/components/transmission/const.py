"""Constants for the Transmission Bittorent Client component."""
DOMAIN = "transmission"

SWITCH_TYPES = {"on_off": "Switch", "turtle_mode": "Turtle Mode"}

ORDER_AGE = "age"
ORDER_AGE_DESC = "age_desc"
ORDER_ID = "id"
ORDER_ID_DESC = "id_desc"
ORDER_RATIO = "ratio"
ORDER_RATIO_DESC = "ratio_desc"

SUPPORTED_ORDER_MODES = [
    ORDER_AGE,
    ORDER_AGE_DESC,
    ORDER_ID,
    ORDER_ID_DESC,
    ORDER_RATIO,
    ORDER_RATIO_DESC,
]

CONF_LIMIT = "limit"
CONF_ORDER = "order"

DEFAULT_DELETE_DATA = False
DEFAULT_LIMIT = 10
DEFAULT_ORDER = ORDER_AGE_DESC
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
