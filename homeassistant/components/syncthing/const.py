"""Constants for the syncthing integration."""
from datetime import timedelta

DOMAIN = "syncthing"
DEFAULT_NAME = "syncthing"
DEFAULT_PORT = 8384

CONF_USE_HTTPS = "use_https"
DEFAULT_USE_HTTPS = False

RECONNECT_INTERVAL = timedelta(seconds=10)

FOLDER_SUMMARY_RECEIVED = "syncthing_folder_summary_received"
STATE_CHANGED_RECEIVED = "syncthing_state_changed_received"
FOLDER_PAUSED_RECEIVED = "syncthing_folder_paused_received"
SERVER_UNAVAILABLE = "syncthing_server_unavailable"

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
