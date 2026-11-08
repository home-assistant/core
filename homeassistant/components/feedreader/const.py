"""Constants for RSS/Atom feeds."""

from datetime import timedelta
from typing import Final

from homeassistant.const import APPLICATION_NAME, __version__ as ha_version

DOMAIN: Final[str] = "feedreader"

CONF_MAX_ENTRIES: Final[str] = "max_entries"
DEFAULT_MAX_ENTRIES: Final[int] = 20
DEFAULT_SCAN_INTERVAL: Final[timedelta] = timedelta(hours=1)

EVENT_FEEDREADER: Final[str] = "feedreader"

USER_AGENT: Final[str] = f"{APPLICATION_NAME}/{ha_version}"
