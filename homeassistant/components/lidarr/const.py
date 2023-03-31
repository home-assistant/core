"""Constants for Lidarr."""
import logging
from typing import Final

from homeassistant.const import UnitOfInformation

BYTE_SIZES = [
    UnitOfInformation.BYTES,
    UnitOfInformation.KILOBYTES,
    UnitOfInformation.MEGABYTES,
    UnitOfInformation.GIGABYTES,
    UnitOfInformation.TERABYTES,
    UnitOfInformation.PETABYTES,
    UnitOfInformation.EXABYTES,
    UnitOfInformation.ZETTABYTES,
    UnitOfInformation.YOTTABYTES,
]

# Defaults
DEFAULT_NAME = "Lidarr"
DEFAULT_UNIT = UnitOfInformation.GIGABYTES
DEFAULT_MAX_RECORDS = 20

DOMAIN: Final = "lidarr"

LOGGER = logging.getLogger(__package__)
