"""Backup platform for the kitchen_sink integration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.backup import Backup, BackupSyncAgent, SyncedBackup
from homeassistant.core import HomeAssistant

LOGGER = logging.getLogger(__name__)


async def async_get_backup_sync_agents(
    hass: HomeAssistant,
) -> list[BackupSyncAgent]:
    """Register the backup sync agents."""
    return [KitchenSinkBackupSyncAgent("syncer")]


class KitchenSinkBackupSyncAgent(BackupSyncAgent):
    """Kitchen sink backup sync agent."""

    async def async_download_backup(
        self,
        *,
        id: str,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file."""
        LOGGER.info("Downloading backup %s to %s", id, path)

    async def async_upload_backup(self, *, backup: Backup, **kwargs: Any) -> None:
        """Upload a backup file."""
        LOGGER.info("Uploading backup %s", backup.slug)

    async def async_list_backups(self, **kwargs: Any) -> list[SyncedBackup]:
        """List synced backups."""
        return [
            SyncedBackup(
                id="def456",
                name="Kitchen sink syncer",
                slug="abc123",
                size=1234,
                date="1970-01-01T00:00:00Z",
            )
        ]
