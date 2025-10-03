"""Constants for CalDAV."""

from typing import Final

DOMAIN: Final = "caldav"

CONF_LEGACY_ENTITY_NAMES = "legacy_entity_names"

CONF_READ_ONLY: Final = "read_only"

# Scan interval
DEFAULT_SCAN_INTERVAL = 900  # seconds
MIN_SCAN_INTERVAL = 15  # seconds
MAX_SCAN_INTERVAL = 3600  # seconds

# Values shown in dropdown (seconds)
SCAN_INTERVAL_OPTIONS = [
    15,
    30,
    60,  # 1 min
    300,  # 5 min
    900,  # 15 min (default)
    1800,  # 30 min
    3600,  # 1 hour
]
