"""Constants for the syncthing integration."""

from datetime import timedelta

DOMAIN = "syncthing"

DEFAULT_VERIFY_SSL = True
DEFAULT_URL = "http://127.0.0.1:8384"

RECONNECT_INTERVAL = timedelta(seconds=10)
SCAN_INTERVAL = timedelta(seconds=120)

DEVICE_CONNECTED_RECEIVED = "syncthing_device_connected_received"
DEVICE_DISCONNECTED_RECEIVED = "syncthing_device_disconnected_received"
DEVICE_PAUSED_RECEIVED = "syncthing_device_paused_received"
DEVICE_RESUMED_RECEIVED = "syncthing_device_resumed_received"
FOLDER_SUMMARY_RECEIVED = "syncthing_folder_summary_received"
FOLDER_PAUSED_RECEIVED = "syncthing_folder_paused_received"
INITIAL_EVENTS_READY = "syncthing_initial_events_ready"
SERVER_UNAVAILABLE = "syncthing_server_unavailable"
SERVER_AVAILABLE = "syncthing_server_available"
STATE_CHANGED_RECEIVED = "syncthing_state_changed_received"

DEVICE_EVENTS = {
    "DeviceConnected": DEVICE_CONNECTED_RECEIVED,
    "DeviceDisconnected": DEVICE_DISCONNECTED_RECEIVED,
    "DevicePaused": DEVICE_PAUSED_RECEIVED,
    "DeviceResumed": DEVICE_RESUMED_RECEIVED,
}

FOLDER_EVENTS = {
    "FolderSummary": FOLDER_SUMMARY_RECEIVED,
    "StateChanged": STATE_CHANGED_RECEIVED,
    "FolderPaused": FOLDER_PAUSED_RECEIVED,
}
