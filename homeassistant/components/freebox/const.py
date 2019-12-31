"""Freebox component constants."""
import socket

DOMAIN = "freebox"
TRACKER_UPDATE = f"{DOMAIN}_tracker_update"

APP_DESC = {
    "app_id": "hass",
    "app_name": "Home Assistant",
    "app_version": "0.104",
    "device_name": socket.gethostname(),
}
API_VERSION = "v6"
CONFIG_FILE = "freebox.conf"

PLATFORMS = ["device_tracker", "sensor", "switch"]

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
