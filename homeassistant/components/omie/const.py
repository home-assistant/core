"""Constants for the OMIE - Spain and Portugal electricity prices integration."""
from datetime import timedelta
from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "omie"
DEFAULT_NAME: Final = "OMIE"
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)
DEFAULT_TIMEOUT = timedelta(seconds=10)

CET = ZoneInfo("CET")
