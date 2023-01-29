"""Constants for OneTracker."""

from datetime import timedelta
from typing import Final

ATTR_CARRIER: Final = "carrier"
ATTR_CARRIER_NAME: Final = "carrier_name"
ATTR_TIME_UPDATED: Final = "time_updated"
ATTR_TRACKING_ID: Final = "tracking_id"
ATTR_TRACKING_LOCATION: Final = "tracking_location"
ATTR_TRACKING_STATUS_READABLE: Final = "tracking_status_readable"
ATTR_TRACKING_STATUS_DESCRIPTION: Final = "tracking_status_description"
ATTR_TRACKING_TIME_ESTIMATED: Final = "tracking_time_estimated"
ATTR_TRACKING_TIME_DELIVERED: Final = "tracking_time_delivered"

DEFAULT_NAME: Final = "OneTracker"
DOMAIN: Final = "onetracker"

PARALLEL_UPDATES: Final = 1
SCAN_INTERVAL: Final = timedelta(minutes=15)
