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

# Defaults
DEFAULT_DAYS = "1"
DEFAULT_HOST = "localhost"
DEFAULT_NAME = "Lidarr"
DEFAULT_UNIT = DATA_GIGABYTES
DEFAULT_MAX_RECORDS = 20

DOMAIN: Final = "lidarr"

LOGGER = logging.getLogger(__package__)
