"""Constants for the tractive integration."""

from datetime import timedelta

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
    TIME_MINUTES,
)

from .model import TractiveSensorEntityDescription

DOMAIN = "tractive"

RECONNECT_INTERVAL = timedelta(seconds=10)

ATTR_ACTIVITY = "activity"
ATTR_DAILY_GOAL = "daily_goal"
ATTR_HARDWARE = "hardware"
ATTR_MINUTES_ACTIVE = "minutes_active"

TRACKER_HARDWARE_STATUS_UPDATED = "tracker_hardware_status_updated"
TRACKER_POSITION_UPDATED = "tracker_position_updated"
TRACKER_ACTIVITY_STATUS_UPDATED = "tractive_tracker_activity_updated"

SERVER_UNAVAILABLE = "tractive_server_unavailable"

SENSOR_TYPES = (
    TractiveSensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        name="Battery Level",
        unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        event_type=ATTR_HARDWARE,
    ),
    TractiveSensorEntityDescription(
        key=ATTR_MINUTES_ACTIVE,
        name="Minutes Active",
        icon="mdi:clock-time-eight-outline",
        unit_of_measurement=TIME_MINUTES,
        event_type=ATTR_ACTIVITY,
        attributes=(ATTR_DAILY_GOAL,),
    ),
)
