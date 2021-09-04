"""Constants for the tractive integration."""

from datetime import timedelta

DOMAIN = "tractive"

RECONNECT_INTERVAL = timedelta(seconds=10)

ATTR_DAILY_GOAL = "daily_goal"
ATTR_HW_INFO = "hw_info"
ATTR_MINUTES_ACTIVE = "minutes_active"
ATTR_POS_REPORT = "pos_report"
ATTR_TRACKABLE = "trackable"
ATTR_TRACKER_DETAILS = "tracker_details"

CLIENT = "client"
TRACKABLES = "trackables"

TRACKER_HARDWARE_STATUS_UPDATED = f"{DOMAIN}_tracker_hardware_status_updated"
TRACKER_POSITION_UPDATED = f"{DOMAIN}_tracker_position_updated"
TRACKER_ACTIVITY_STATUS_UPDATED = f"{DOMAIN}_tracker_activity_updated"

SERVER_UNAVAILABLE = f"{DOMAIN}_server_unavailable"
