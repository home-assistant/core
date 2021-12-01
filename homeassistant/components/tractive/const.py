"""Constants for the tractive integration."""

from datetime import timedelta

DOMAIN = "tractive"

RECONNECT_INTERVAL = timedelta(seconds=10)

ATTR_DAILY_GOAL = "daily_goal"
ATTR_BUZZER = "buzzer"
ATTR_LED = "led"
ATTR_LIVE_TRACKING = "live_tracking"
ATTR_MINUTES_ACTIVE = "minutes_active"

CLIENT = "client"
TRACKABLES = "trackables"

TRACKER_HARDWARE_STATUS_UPDATED = f"{DOMAIN}_tracker_hardware_status_updated"
TRACKER_POSITION_UPDATED = f"{DOMAIN}_tracker_position_updated"
TRACKER_ACTIVITY_STATUS_UPDATED = f"{DOMAIN}_tracker_activity_updated"

SERVER_UNAVAILABLE = f"{DOMAIN}_server_unavailable"
