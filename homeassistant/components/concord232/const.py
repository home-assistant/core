"""Constants for the Concord232 integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "concord232"

DEFAULT_PORT: Final = 5007
DEFAULT_MODE: Final = "audible"

MODE_AUDIBLE: Final = "audible"
MODE_SILENT: Final = "silent"

UPDATE_INTERVAL: Final = timedelta(seconds=10)
