"""Constants for the Backup integration."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .manager import BackupManager

DOMAIN = "backup"
DATA_MANAGER: HassKey[BackupManager] = HassKey(DOMAIN)
LOGGER = getLogger(__package__)

EXCLUDE_FROM_BACKUP = [
    "__pycache__/*",
    ".DS_Store",
    ".HA_RESTORE",
    "*.db-shm",
    "*.log.*",
    "*.log",
    "backups/*.tar",
    "OZW_Log.txt",
    "tts/*",
]
