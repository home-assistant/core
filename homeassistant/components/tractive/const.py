"""Constants for the tractive integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "tractive"

RECONNECT_INTERVAL: Final = timedelta(seconds=10)

ATTR_DAILY_GOAL: Final = "daily_goal"
ATTR_BUZZER: Final = "buzzer"
ATTR_LED: Final = "led"
ATTR_LIVE_TRACKING: Final = "live_tracking"
ATTR_MINUTES_ACTIVE: Final = "minutes_active"

CLIENT: Final = "client"
TRACKABLES: Final = "trackables"

TRACKER_HARDWARE_STATUS_UPDATED: Final = f"{DOMAIN}_tracker_hardware_status_updated"
TRACKER_POSITION_UPDATED: Final = f"{DOMAIN}_tracker_position_updated"
TRACKER_ACTIVITY_STATUS_UPDATED: Final = f"{DOMAIN}_tracker_activity_updated"

SERVER_UNAVAILABLE: Final = f"{DOMAIN}_server_unavailable"
