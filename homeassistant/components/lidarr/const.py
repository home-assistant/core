"""Constants for Lidarr."""
import logging
from typing import Final

from homeassistant.const import (
    DATA_BYTES,
    DATA_EXABYTES,
    DATA_GIGABYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_PETABYTES,
    DATA_TERABYTES,
    DATA_YOTTABYTES,
    DATA_ZETTABYTES,
)

BYTE_SIZES = [
    DATA_BYTES,
    DATA_KILOBYTES,
    DATA_MEGABYTES,
    DATA_GIGABYTES,
    DATA_TERABYTES,
    DATA_PETABYTES,
    DATA_EXABYTES,
    DATA_ZETTABYTES,
    DATA_YOTTABYTES,
]

# Config Keys
CONF_MAX_RECORDS = "max_records"
CONF_UPCOMING_DAYS = "upcoming_days"

# Defaults
DEFAULT_DAYS = "1"
DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Lidarr"
DEFAULT_UNIT = DATA_GIGABYTES
DEFAULT_MAX_RECORDS = 1000
DEFAULT_UPCOMING_DAYS = 7
DEFAULT_URL = "http://127.0.0.1:8686"

DOMAIN: Final = "lidarr"

LOGGER = logging.getLogger(__package__)
