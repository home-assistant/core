"""Constants for the Backup integration."""
from logging import getLogger

DOMAIN = "backup"
LOGGER = getLogger(__package__)

ATTR_KEEP_RECENT = "keep_recent"

EXCLUDE_FROM_BACKUP = [
    "__pycache__/*",
    ".DS_Store",
    "*.db-shm",
    "*.log.*",
    "*.log",
    "backups/*.tar",
    "OZW_Log.txt",
]
