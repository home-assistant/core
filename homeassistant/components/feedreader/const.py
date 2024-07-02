"""Constants for RSS/Atom feeds."""

from datetime import timedelta

DOMAIN = "feedreader"

CONF_MAX_ENTRIES = "max_entries"
DEFAULT_MAX_ENTRIES = 20
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)
