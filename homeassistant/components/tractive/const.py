"""Constants for the tractive integration."""

from datetime import timedelta

DOMAIN = "tractive"

RECONNECT_INTERVAL = timedelta(seconds=10)

TRACKER_HARDWARE_STATUS_UPDATED = "tractive_tracker_hardware_status_updated"
TRACKER_POSITION_UPDATED = "tractive_tracker_position_updated"

SERVER_UNAVAILABLE = "tractive_server_unavailable"
