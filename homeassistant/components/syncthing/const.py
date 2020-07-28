"""Constants for the syncthing integration."""
from datetime import timedelta

DOMAIN = "syncthing"
DEFAULT_NAME = "syncthing"

DEFAULT_VERIFY_SSL = True

DEFAULT_URL = "http://127.0.0.1:8384"

RECONNECT_INTERVAL = timedelta(seconds=10)
SCAN_INTERVAL = timedelta(seconds=120)

FOLDER_SUMMARY_RECEIVED = "syncthing_folder_summary_received"
FOLDER_PAUSED_RECEIVED = "syncthing_folder_paused_received"
SERVER_UNAVAILABLE = "syncthing_server_unavailable"
SERVER_AVAILABLE = "syncthing_server_available"
STATE_CHANGED_RECEIVED = "syncthing_state_changed_received"

EVENTS = {
    "FolderSummary": FOLDER_SUMMARY_RECEIVED,
    "StateChanged": STATE_CHANGED_RECEIVED,
    "FolderPaused": FOLDER_PAUSED_RECEIVED,
}


FOLDER_SENSOR_ICONS = {
    "paused": "mdi:folder-clock",
    "scanning": "mdi:folder-search",
    "syncing": "mdi:folder-sync",
    "idle": "mdi:folder",
}

FOLDER_SENSOR_ALERT_ICON = "mdi:folder-alert"
FOLDER_SENSOR_DEFAULT_ICON = "mdi:folder"
