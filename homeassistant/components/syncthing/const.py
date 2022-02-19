"""Constants for the syncthing integration."""
from datetime import timedelta

DOMAIN = "syncthing"

DEFAULT_VERIFY_SSL = True
DEFAULT_URL = "http://127.0.0.1:8384"

RECONNECT_INTERVAL = timedelta(seconds=10)
SCAN_INTERVAL = timedelta(seconds=120)

FOLDER_SUMMARY_RECEIVED = "syncthing_folder_summary_received"
FOLDER_PAUSED_RECEIVED = "syncthing_folder_paused_received"
SERVER_UNAVAILABLE = "syncthing_server_unavailable"
SERVER_AVAILABLE = "syncthing_server_available"
STATE_CHANGED_RECEIVED = "syncthing_state_changed_received"

FOLDER_EVENTS = {
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

DEVICE_PAUSED = "syncthing_device_paused"
DEVICE_RESUMED = "syncthing_device_resumed"
DEVICE_CONNECTED = "syncthing_device_connected"
DEVICE_DISCONNECTED = "syncthing_device_disconnected"
DEVICE_SUMMARY_RECEIVED = "syncthing_device_summary_received"

DEVICE_EVENTS = {
    "DeviceConnected": DEVICE_CONNECTED,
    "DeviceDisconnected": DEVICE_DISCONNECTED,
    "DevicePaused": DEVICE_PAUSED,
    "DeviceResumed": DEVICE_RESUMED,
}

DEVICE_SENSOR_ICONS = {
    "connected": "mdi:lan-connect",
    "disconnected": "mdi:lan-disconnect",
}

DEVICE_SENSOR_ALERT_ICON = "mdi:folder-alert"
DEVICE_SENSOR_DEFAULT_ICON = "mdi:devices"
