"""Constants for the Deluge integration."""

import enum
import logging
from typing import Final

CONF_WEB_PORT = "web_port"
DEFAULT_NAME = "Deluge"
DEFAULT_RPC_PORT = 58846
DEFAULT_WEB_PORT = 8112
DOMAIN: Final = "deluge"
LOGGER = logging.getLogger(__package__)


class DelugeGetSessionStatusKeys(enum.Enum):
    """Enum representing the keys that get passed into the Deluge RPC `core.get_session_status` xml rpc method.

    You can call `core.get_session_status` with no keys (so an empty list in deluge-client.DelugeRPCClient.call)
    to get the full list of possible keys, but it seems to basically be a all of the session statistics
    listed on this page: https://www.rasterbar.com/products/libtorrent/manual-ref.html#session-statistics
    and a few others

    there is also a list of deprecated keys that deluge will translate for you and issue a warning in the log:
    https://github.com/deluge-torrent/deluge/blob/7f3f7f69ee78610e95bea07d99f699e9310c4e08/deluge/core/core.py#L58

    """

    DHT_DOWNLOAD_RATE = "dht_download_rate"
    DHT_UPLOAD_RATE = "dht_upload_rate"
    DOWNLOAD_RATE = "download_rate"
    UPLOAD_RATE = "upload_rate"


class DelugeSensorType(enum.StrEnum):
    """Enum that distinguishes the different sensor types that the Deluge integration has.

    This is mainly used to avoid passing strings around and to distinguish between similarly
    named strings in `DelugeGetSessionStatusKeys`.
    """

    CURRENT_STATUS_SENSOR = "current_status"
    DOWNLOAD_SPEED_SENSOR = "download_speed"
    UPLOAD_SPEED_SENSOR = "upload_speed"
    PROTOCOL_TRAFFIC_UPLOAD_SPEED_SENSOR = "protocol_traffic_upload_speed"
    PROTOCOL_TRAFFIC_DOWNLOAD_SPEED_SENSOR = "protocol_traffic_download_speed"
