"""Constants for OneTracker."""

from datetime import timedelta

DOMAIN = "onetracker"

# Attributes
ATTR_SPEED = "speed"
ATTR_TRACKING_ID = "tracking_id"

# Data
DATA_COORDINATOR = "coordinator"
DATA_UNDO_UPDATE_LISTENER = "undo_update_listener"

# Defaults
DEFAULT_NAME = "OneTracker"
DEFAULT_SCAN_INTERVAL = 3600


SCAN_INTERVAL = timedelta(seconds=60)
PARALLEL_UPDATES = 4
