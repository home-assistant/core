"""Constants for qBittorrent."""
from typing import Final

DOMAIN: Final = "qbittorrent"

DEFAULT_NAME = "qBittorrent"
DEFAULT_URL = "http://127.0.0.1:8080"

CONF_CREATE_TORRENT_SENSORS: Final = "create_torrent_sensors"

"""
Normalized states which match with qBittorrent's UI frontend categories:
https://github.com/qbittorrent/qBittorrent/blob/7bd8f262dbcd153685ead13e972afba95b7eff6d/src/webui/www/private/scripts/dynamicTable.js#L967
"""
QBITTORRENT_TORRENT_STATES = {
    "downloading": {"forcedDL", "metaDL", "forcedMetaDL", "downloading"},
    "uploading": {"forcedUP", "uploading"},
    "stalled": {"stalledUP", "stalledDL"},
    "stopped": {"pausedDL"},
    "completed": {"pausedUP"},
    "queued": {"queued"},
    "checking": {
        "checkingDL",
        "checkingUP",
        "queuedForChecking",
        "checkingResumeData",
        "moving",
    },
    "error": {"error", "unknown", "missingFiles"},
}
