"""Constants for the LaCrosse View integration."""

from datetime import timedelta

DOMAIN = "lacrosse_view"
SCAN_INTERVAL = 60
STALE_DATA_THRESHOLD = timedelta(seconds=3600)
