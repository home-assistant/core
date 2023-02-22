"""Constants for the Backup integration."""
from logging import getLogger

DOMAIN = "backup"
LOGGER = getLogger(__package__)

EXCLUDE_FROM_BACKUP = [
    "__pycache__/*",
    ".DS_Store",
    "*.db-shm",
    "*.log.*",
    "*.log",
    "backups/*.tar",
    "OZW_Log.txt",
]
