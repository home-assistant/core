"""Constants for the Backup integration."""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .manager import BackupManager

BUF_SIZE = 2**20 * 4  # 4MB
DOMAIN = "backup"
DATA_MANAGER: HassKey[BackupManager] = HassKey(DOMAIN)
LOGGER = getLogger(__package__)

EXCLUDE_FROM_BACKUP = [
    "**/__pycache__/*",
    "**/.DS_Store",
    ".HA_RESTORE",
    "*.db-shm",
    "*.log.*",
    "*.log",
    "backups/*.tar",
    "tmp_backups/*.tar",
    "OZW_Log.txt",
    "tts/*",
]

EXCLUDE_DATABASE_FROM_BACKUP = [
    "home-assistant_v2.db",
    "home-assistant_v2.db-wal",
]
