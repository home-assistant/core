"""Constants for the Synology SRM integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "synology_srm"

DEFAULT_USERNAME: Final = "admin"
DEFAULT_PORT: Final = 8001
DEFAULT_SSL: Final = True
DEFAULT_VERIFY_SSL: Final = False
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)
