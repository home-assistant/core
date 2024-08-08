"""Constants for the mütesync integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "mutesync"

UPDATE_INTERVAL_NOT_IN_MEETING: Final = timedelta(seconds=10)
UPDATE_INTERVAL_IN_MEETING: Final = timedelta(seconds=10)
