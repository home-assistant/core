"""Constants for the tractive integration."""

from datetime import timedelta

DOMAIN = "tractive"

RECONNECT_INTERVAL = timedelta(seconds=10)

ATTR_BUZZER = "buzzer"
ATTR_CALORIES = "calories"
ATTR_DAILY_GOAL = "daily_goal"
ATTR_LED = "led"
ATTR_LIVE_TRACKING = "live_tracking"
ATTR_MINUTES_ACTIVE = "minutes_active"
ATTR_MINUTES_DAY_SLEEP = "minutes_day_sleep"
ATTR_MINUTES_NIGHT_SLEEP = "minutes_night_sleep"
ATTR_MINUTES_REST = "minutes_rest"
ATTR_TRACKER_STATE = "tracker_state"

# This client ID was issued by Tractive specifically for Home Assistant.
# Please do not use it anywhere else.
CLIENT_ID = "625e5349c3c3b41c28a669f1"

CLIENT = "client"
TRACKABLES = "trackables"

TRACKER_HARDWARE_STATUS_UPDATED = f"{DOMAIN}_tracker_hardware_status_updated"
TRACKER_POSITION_UPDATED = f"{DOMAIN}_tracker_position_updated"
TRACKER_ACTIVITY_STATUS_UPDATED = f"{DOMAIN}_tracker_activity_updated"
TRACKER_WELLNESS_STATUS_UPDATED = f"{DOMAIN}_tracker_wellness_updated"

SERVER_UNAVAILABLE = f"{DOMAIN}_server_unavailable"
