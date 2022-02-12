"""Constants for the Backup integration."""
from logging import getLogger

from awesomeversion import AwesomeVersion

from homeassistant.const import __version__ as HAVERSION

DOMAIN = "backup"
HA_VERSION_OBJ = AwesomeVersion(HAVERSION)
LOGGER = getLogger(__package__)

EXCLUDE_FROM_BACKUP = [
    "__pycache__/*",
    "*.db-shm",
    "*.log.*",
    "*.log",
    "backups/*.tar",
    "OZW_Log.txt",
]
