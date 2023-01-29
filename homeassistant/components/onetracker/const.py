"""Constants for OneTracker."""

from datetime import timedelta

ATTR_CARRIER = "carrier"
ATTR_CARRIER_NAME = "carrier_name"
ATTR_TIME_UPDATED = "time_updated"
ATTR_TRACKING_ID = "tracking_id"
ATTR_TRACKING_LOCATION = "tracking_location"
ATTR_TRACKING_STATUS_READABLE = "tracking_status_readable"
ATTR_TRACKING_STATUS_DESCRIPTION = "tracking_status_description"
ATTR_TRACKING_TIME_ESTIMATED = "tracking_time_estimated"
ATTR_TRACKING_TIME_DELIVERED = "tracking_time_delivered"

DEFAULT_NAME = "OneTracker"
DOMAIN = "onetracker"

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(minutes=15)
