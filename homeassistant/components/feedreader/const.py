"""Constants for RSS/Atom feeds."""

from datetime import timedelta

CONF_URLS = "urls"
CONF_MAX_ENTRIES = "max_entries"

DEFAULT_MAX_ENTRIES = 20
DEFAULT_SCAN_INTERVAL = timedelta(hours=1)
DELAY_SAVE = 30

DOMAIN = "feedreader"

EVENT_FEEDREADER = "feedreader"
STORAGE_VERSION = 1
